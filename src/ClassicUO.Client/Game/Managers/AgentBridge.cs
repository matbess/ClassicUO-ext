// SPDX-License-Identifier: BSD-2-Clause

using ClassicUO.Configuration;
using ClassicUO.Game.Data;
using ClassicUO.Game.GameObjects;
using ClassicUO.Game.UI.Gumps;
using ClassicUO.Utility;
using ClassicUO.Utility.Logging;
using Microsoft.Xna.Framework;
using System;
using System.Buffers;
using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace ClassicUO.Game.Managers
{
    // Local HTTP interface that lets an agent (Claude) look at the game and act as the logged-in character.
    // Off unless the character's profile enables it. Listens on 127.0.0.1 only and needs the token
    // written to Agent/<character>.json next to the client. Requests are carried out on the game thread.
    // Anything that changes the game is limited by Agent/rules.json: the area the agent may work in,
    // containers it must leave alone and items it must never pick up. It also pauses while anyone
    // else is in that area. Actions are paced like a person playing: a random gap between each, and a
    // longer break after every few. Anything out of reach is refused before it is sent (the server
    // ignores it silently), and if the server ever doesn't answer, the bridge stops until told to resume.
    internal sealed class AgentBridge
    {
        private const int FIRST_PORT = 7780;
        private const int LAST_PORT = 7789;
        private const int VERSION = 1;
        private const int GAME_THREAD_TIMEOUT = 5000;
        private const int POLL_INTERVAL = 50;
        private const int OPEN_TIMEOUT = 3000;
        private const int NAME_TIMEOUT = 1500;
        private const int SETTLE_TIME = 300; // more packets usually follow the first reply within this time
        private const int MAX_MESSAGES = 500;
        private const int MAX_HEADER_BYTES = 8192;
        private const int MAX_RANGE = 24;
        private const int MAX_DEPTH = 4;
        private const int REACH = 2; // the server silently ignores a double-click or lift from further away
        private const int TARGET_REACH = 12;
        private const int LIFT_WAIT = 250; // time for the server to refuse a lift before the drop is sent
        private const int MOVE_TIMEOUT = 3000;
        private const int TARGET_TIMEOUT = 3000;
        private const int USE_RESULT_TIMEOUT = 2000;
        private const int WALK_TIMEOUT = 20000;
        private const string MUST_WAIT = "You must wait to perform another action";

        private readonly World _world;
        private readonly ConcurrentQueue<Action> _work = new ConcurrentQueue<Action>();

        // only touched on the game thread
        private readonly Queue<Message> _messages = new Queue<Message>();
        private readonly Dictionary<uint, Label> _labels = new Dictionary<uint, Label>();
        private readonly Dictionary<uint, ushort> _containerGumps = new Dictionary<uint, ushort>(); // which gump the server showed for a container
        private readonly Dictionary<uint, long> _containerAnswers = new Dictionary<uint, long>(); // last time the server showed a container or sent its contents
        private long _packetCount;
        private long _lastMessageId;
        private TcpListener _listener;
        private string _infoPath;
        private uint _playerSerial;
        private uint _failedSerial;

        // only touched on the listener thread
        private readonly Random _random = new Random();
        private DateTime _nextAction;
        private int _burstCount;
        private string _halted;
        private Rules _rules;
        private DateTime _rulesTime;

        public AgentBridge(World world)
        {
            _world = world;
            _world.MessageManager.MessageReceived += OnMessage;
            AppDomain.CurrentDomain.ProcessExit += (s, e) => DeleteInfoFile();
        }

        public void Update()
        {
            Profile profile = ProfileManager.CurrentProfile;
            uint player = _world.Player?.Serial ?? 0;

            if (profile == null || !profile.AgentBridge || player == 0)
            {
                _failedSerial = 0;

                if (_listener != null)
                {
                    Stop();
                }
            }
            else if ((_listener == null || _playerSerial != player) && _failedSerial != player)
            {
                Start(profile.CharacterName, player);
            }

            while (_work.TryDequeue(out Action action))
            {
                action();
            }
        }

        // server packets, on the game thread: note when a container is shown (0x24) or its contents arrive (0x3C).
        // Opening a container the server still counts as open (closing a window isn't sent to the server)
        // can bring only its contents, so either one answers an open.
        public void OnPacket(ReadOnlySpan<byte> data)
        {
            if (_listener == null || data.Length < 5)
            {
                return;
            }

            switch (data[0])
            {
                case 0x24:
                    _containerAnswers[BinaryPrimitives.ReadUInt32BigEndian(data.Slice(1))] = ++_packetCount;

                    break;

                case 0x3C:
                    int count = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(3));

                    if (count > 0 && (data.Length - 5) % count == 0)
                    {
                        // each entry ends with the container serial and a hue
                        int size = (data.Length - 5) / count;

                        for (int i = 0; i < count; i++)
                        {
                            _containerAnswers[BinaryPrimitives.ReadUInt32BigEndian(data.Slice(5 + i * size + size - 6))] = ++_packetCount;
                        }
                    }

                    break;
            }
        }

        public void Stop()
        {
            if (_listener == null)
            {
                return;
            }

            try
            {
                _listener.Stop();
            }
            catch (Exception ex)
            {
                Log.Warn($"Agent bridge: {ex.Message}");
            }

            _listener = null;
            _playerSerial = 0;
            _messages.Clear();
            _labels.Clear();
            _containerGumps.Clear();
            _containerAnswers.Clear();
            DeleteInfoFile();
            Log.Info("Agent bridge stopped");
        }

        private void Start(string characterName, uint player)
        {
            Stop();

            TcpListener listener = null;
            int port = FIRST_PORT;

            for (; port <= LAST_PORT; port++)
            {
                try
                {
                    listener = new TcpListener(IPAddress.Loopback, port);
                    listener.Start();

                    break;
                }
                catch (SocketException)
                {
                    listener = null;
                }
            }

            if (listener == null)
            {
                Log.Error($"Agent bridge: no free port between {FIRST_PORT} and {LAST_PORT}");
                _failedSerial = player;

                return;
            }

            byte[] token = RandomNumberGenerator.GetBytes(32);

            try
            {
                WriteInfoFile(characterName, player, port, Convert.ToHexString(token));
            }
            catch (Exception ex)
            {
                Log.Error($"Agent bridge: could not write its info file: {ex.Message}");
                listener.Stop();
                _failedSerial = player;

                return;
            }

            _listener = listener;
            _playerSerial = player;

            new Thread(() => Listen(listener, Encoding.ASCII.GetBytes(Convert.ToHexString(token))))
            {
                IsBackground = true,
                Name = "AgentBridge"
            }.Start();

            Log.Info($"Agent bridge listening on 127.0.0.1:{port}");
        }

        private void WriteInfoFile(string characterName, uint player, int port, string token)
        {
            string name = string.IsNullOrEmpty(characterName) ? "unknown" : characterName;

            foreach (char c in Path.GetInvalidFileNameChars())
            {
                name = name.Replace(c, '_');
            }

            string folder = FileSystemHelper.CreateFolderIfNotExists(CUOEnviroment.ExecutablePath, "Agent");
            string path = Path.Combine(folder, name + ".json");

            File.WriteAllBytes
            (
                path,
                Json
                (
                    w =>
                    {
                        w.WriteStartObject();
                        w.WriteString("character", characterName);
                        w.WriteString("serial", Hex(player));
                        w.WriteNumber("port", port);
                        w.WriteString("token", token);
                        w.WriteString("started", DateTime.Now.ToString("s", CultureInfo.InvariantCulture));
                        w.WriteEndObject();
                    }
                )
            );

            _infoPath = path;
        }

        private void DeleteInfoFile()
        {
            string path = _infoPath;
            _infoPath = null;

            if (path == null)
            {
                return;
            }

            try
            {
                File.Delete(path);
            }
            catch (Exception ex)
            {
                Log.Warn($"Agent bridge: could not delete {path}: {ex.Message}");
            }
        }

        private void OnMessage(object sender, MessageEventArgs e)
        {
            if (_listener == null || string.IsNullOrEmpty(e.Text))
            {
                return;
            }

            DateTime now = DateTime.Now;
            uint serial = e.Parent?.Serial ?? 0;

            _messages.Enqueue
            (
                new Message
                {
                    Id = ++_lastMessageId,
                    Time = now,
                    Serial = serial,
                    Name = e.Name,
                    Type = e.Type,
                    Text = e.Text
                }
            );

            while (_messages.Count > MAX_MESSAGES)
            {
                _messages.Dequeue();
            }

            // a single click can answer with several lines, such as a name and then its charges
            if (e.Type == MessageType.Label && e.Parent is Item)
            {
                if (!_labels.TryGetValue(serial, out Label label) || (now - label.Time).TotalMilliseconds > 1000)
                {
                    _labels[serial] = label = new Label();
                }

                label.Lines.Add(e.Text);
                label.Time = now;
            }
        }

        // ---- requests, on the listener thread ----

        private void Listen(TcpListener listener, byte[] token)
        {
            while (true)
            {
                TcpClient client;

                try
                {
                    client = listener.AcceptTcpClient();
                }
                catch (Exception)
                {
                    return; // stopped
                }

                using (client)
                {
                    try
                    {
                        client.ReceiveTimeout = 5000;
                        client.SendTimeout = 5000;
                        Serve(client.GetStream(), token);
                    }
                    catch (Exception ex)
                    {
                        Log.Warn($"Agent bridge: {ex.Message}");
                    }
                }
            }
        }

        private void Serve(NetworkStream stream, byte[] token)
        {
            string head = ReadHead(stream);

            if (head == null)
            {
                return;
            }

            string[] lines = head.Split("\r\n");
            string[] request = lines[0].Split(' ');

            if (request.Length < 3)
            {
                Respond(stream, 400, Error("bad request"));

                return;
            }

            string authorization = null;
            bool fromBrowser = false;

            for (int i = 1; i < lines.Length; i++)
            {
                int colon = lines[i].IndexOf(':');

                if (colon <= 0)
                {
                    continue;
                }

                string key = lines[i].Substring(0, colon).Trim();
                string value = lines[i].Substring(colon + 1).Trim();

                if (key.Equals("Authorization", StringComparison.OrdinalIgnoreCase))
                {
                    authorization = value;
                }
                else if (key.Equals("Origin", StringComparison.OrdinalIgnoreCase) || key.StartsWith("Sec-Fetch-", StringComparison.OrdinalIgnoreCase))
                {
                    fromBrowser = true;
                }
            }

            // web pages can reach localhost too; they never get the token, and are refused outright
            if (fromBrowser)
            {
                Respond(stream, 403, Error("requests from web pages are not accepted"));

                return;
            }

            if (!IsAuthorized(authorization, token))
            {
                Respond(stream, 401, Error("missing or wrong token"));

                return;
            }

            string target = request[1];
            int q = target.IndexOf('?');
            string path = q < 0 ? target : target.Substring(0, q);
            Dictionary<string, string> query = ParseQuery(q < 0 ? "" : target.Substring(q + 1));

            int status = 200;
            byte[] body;

            try
            {
                body = Handle(request[0], path, query);
            }
            catch (BridgeException ex)
            {
                status = ex.Status;
                body = Error(ex.Message);
            }

            Respond(stream, status, body);
        }

        private byte[] Handle(string method, string path, Dictionary<string, string> query)
        {
            switch (path)
            {
                case "/status":
                    RequireMethod(method, "GET");
                    string halted = _halted;

                    return OnGame(() => Json(w => WriteStatus(w, halted)));

                case "/nearby":
                    RequireMethod(method, "GET");
                    int range = Math.Clamp(GetInt(query, "range", 12), 0, MAX_RANGE);
                    bool containersOnly = GetInt(query, "containers", 0) != 0;

                    return OnGame(() => Json(w => WriteNearby(w, range, containersOnly)));

                case "/item":
                    RequireMethod(method, "GET");
                    uint itemSerial = GetSerial(query);

                    return OnGame(() => Json(w => WriteItemDetails(w, itemSerial)));

                case "/contents":
                    RequireMethod(method, "GET");
                    uint containerSerial = GetSerial(query);
                    int depth = Math.Clamp(GetInt(query, "depth", 1), 1, MAX_DEPTH);

                    return OnGame(() => Json(w => WriteContents(w, containerSerial, depth, 0)));

                case "/messages":
                    RequireMethod(method, "GET");
                    long after = GetLong(query, "after", 0);

                    return OnGame(() => Json(w => WriteMessages(w, after)));

                case "/open":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Open(GetSerial(query));

                case "/name":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Name(GetSerials(query));

                case "/close":
                    RequireMethod(method, "POST");
                    uint closeSerial = GetSerial(query);

                    return OnGame(() => Json(w => WriteDone(w, CloseContainer(closeSerial))));

                case "/cancel":
                    RequireMethod(method, "POST");

                    return OnGame(() => Json(w => WriteDone(w, CancelTarget())));

                case "/resume":
                    RequireMethod(method, "POST");
                    bool wasHalted = _halted != null;
                    _halted = null;
                    _burstCount = 0;

                    return Json(w => WriteDone(w, wasHalted));

                case "/rules":
                    RequireMethod(method, "GET");
                    Rules current = RequireRules();

                    return Json(w => current.Write(w));

                case "/walk":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Walk(query);

                case "/move":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Move(GetSerial(query), GetSerial(query, "to"), GetInt(query, "x", 0xFFFF), GetInt(query, "y", 0xFFFF), GetInt(query, "amount", 0));

                case "/equip":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Equip(GetSerial(query));

                case "/use":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Use(GetSerial(query), GetSerial(query, "target"));
            }

            throw new BridgeException(404, $"unknown request {path}");
        }

        // double-clicks a container and waits for the server to show it
        private byte[] Open(uint serial)
        {
            long before = 0;
            long packetsBefore = 0;
            bool wasOpen = false;
            bool opened = false;

            for (int attempt = 0; attempt < 2 && !opened; attempt++)
            {
                WaitForActionSlot();

                (before, wasOpen, packetsBefore) = OnGame
                (
                    () =>
                    {
                        Item item = _world.Items.Get(serial);

                        if (item == null)
                        {
                            throw new BridgeException(404, "no such item nearby");
                        }

                        // double-clicking anything else can use it up (a potion is drunk, a wand fires)
                        if (!item.ItemData.IsContainer || item.IsCorpse)
                        {
                            throw new BridgeException(403, "only containers can be opened");
                        }

                        CheckInReach(GroundRoot(item), REACH);

                        bool open = item.Opened && UIManager.GetGump<ContainerGump>(serial) != null;
                        GameActions.DoubleClick(_world, serial);

                        return (_lastMessageId, open, _packetCount);
                    }
                );

                opened = wasOpen || WaitFor(() => ContainerAnswered(serial, packetsBefore) || SawMessage(before, MUST_WAIT), OPEN_TIMEOUT)
                    && OnGame(() => ContainerAnswered(serial, packetsBefore));

                if (!opened && !OnGame(() => SawMessage(before, MUST_WAIT)))
                {
                    break;
                }
            }

            if (!opened && !OnGame(() => HasSystemMessageAfter(before)))
            {
                Halt($"no answer when opening {Hex(serial)}");
            }

            Thread.Sleep(SETTLE_TIME);

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        RememberContainerGump(serial);
                        w.WriteStartObject();
                        w.WriteBoolean("opened", opened);
                        WriteMessagesSince(w, before, 0);

                        if (opened)
                        {
                            w.WritePropertyName("contents");
                            WriteContents(w, serial, 1, 0);
                        }

                        w.WriteEndObject();
                    }
                )
            );
        }

        // single-clicks items and returns the names the server answers with
        private byte[] Name(List<uint> serials)
        {
            var results = new List<(uint Serial, long Before, bool Answered)>();

            foreach (uint serial in serials)
            {
                WaitForActionSlot();

                long before = OnGame
                (
                    () =>
                    {
                        if (_world.Get(serial) == null)
                        {
                            throw new BridgeException(404, $"no such item nearby: {Hex(serial)}");
                        }

                        _labels.Remove(serial);
                        GameActions.SingleClick(_world, serial);

                        return _lastMessageId;
                    }
                );

                bool answered = WaitFor(() => HasMessageFrom(serial, before), NAME_TIMEOUT);

                if (!answered)
                {
                    Halt($"no answer when asking the name of {Hex(serial)}");
                }

                Thread.Sleep(SETTLE_TIME);

                results.Add((serial, before, answered));
            }

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        w.WriteStartArray();

                        foreach ((uint serial, long before, bool answered) in results)
                        {
                            w.WriteStartObject();
                            w.WriteString("serial", Hex(serial));
                            w.WriteBoolean("answered", answered);
                            w.WriteStartArray("lines");

                            foreach (Message m in _messages)
                            {
                                if (m.Id > before && m.Serial == serial)
                                {
                                    w.WriteStringValue(m.Text);
                                }
                            }

                            w.WriteEndArray();
                            w.WriteEndObject();
                        }

                        w.WriteEndArray();
                    }
                )
            );
        }

        // walks to a spot (x, y) or up to an item (to), inside the agent's area
        private byte[] Walk(Dictionary<string, string> query)
        {
            Rules rules = RequireRules();
            bool toItem = query.ContainsKey("to");
            uint target = toItem ? GetSerial(query, "to") : 0;
            int x = toItem ? 0 : GetRequiredInt(query, "x");
            int y = toItem ? 0 : GetRequiredInt(query, "y");
            int distance = Math.Clamp(GetInt(query, "distance", toItem ? 1 : 0), 0, 10);

            (int destX, int destY, bool already) = OnGame
            (
                () =>
                {
                    CheckNobodyElse(rules);
                    PlayerMobile p = _world.Player;
                    int dx = x, dy = y;

                    if (toItem)
                    {
                        Item item = _world.Items.Get(target) ?? throw new BridgeException(404, "no such item nearby");
                        Item root = CheckReachable(item, rules, "walk to");

                        if (root == null)
                        {
                            return (p.X, p.Y, true); // carried by the character
                        }

                        dx = root.X;
                        dy = root.Y;
                    }
                    else if (!rules.Contains(_world.MapIndex, dx, dy, p.Z))
                    {
                        throw new BridgeException(403, "that spot is outside the agent's area");
                    }

                    if (Math.Max(Math.Abs(p.X - dx), Math.Abs(p.Y - dy)) <= distance)
                    {
                        return (dx, dy, true);
                    }

                    if (!p.Pathfinder.WalkTo(dx, dy, p.Z, distance))
                    {
                        throw new BridgeException(409, "no path to there");
                    }

                    return (dx, dy, false);
                }
            );

            if (!already)
            {
                Thread.Sleep(POLL_INTERVAL * 2);
                WaitFor(() => !_world.Player.Pathfinder.AutoWalking, WALK_TIMEOUT);
            }

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        PlayerMobile p = _world.Player;
                        int left = Math.Max(Math.Abs(p.X - destX), Math.Abs(p.Y - destY));

                        w.WriteStartObject();
                        w.WriteBoolean("arrived", left <= distance);
                        w.WriteNumber("x", p.X);
                        w.WriteNumber("y", p.Y);
                        w.WriteNumber("z", p.Z);
                        w.WriteNumber("tilesLeft", left);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // picks an item up and drops it into a container (at x, y in its gump) or onto a stack of the same kind;
        // with an amount, only that many are taken from a stack: the part moved keeps the serial and the rest
        // stays behind as a new item
        private byte[] Move(uint serial, uint to, int x, int y, int amount)
        {
            Rules rules = RequireRules();

            // dropping onto a stack merges the item into it, so the item itself never comes back
            (bool ontoStack, int targetAmount) = OnGame
            (
                () =>
                {
                    Item target = _world.Items.Get(to);

                    return (target != null && !target.ItemData.IsContainer, target?.Amount ?? 0);
                }
            );

            long before = Lift(serial, rules, item => CheckDropTarget(item, _world.Items.Get(to), rules), amount);

            OnGame
            (
                () =>
                {
                    GameActions.DropItem(serial, x, y, 0, to);

                    return true;
                }
            );

            // the server counts its one action a second from the drop too
            PaceFromNow();

            bool answered = WaitFor(() => _world.Items.Get(serial) != null || ontoStack && (_world.Items.Get(to)?.Amount ?? 0) > targetAmount, MOVE_TIMEOUT);
            Thread.Sleep(SETTLE_TIME);

            if (!answered && !OnGame(() => HasSystemMessageAfter(before)))
            {
                OnGame
                (
                    () =>
                    {
                        ReleaseHeldItem();

                        return true;
                    }
                );

                Halt($"no answer after dropping {Hex(serial)}");
            }

            return OnGame
            (
                () =>
                {
                    Item item = _world.Items.Get(serial);
                    bool merged = item == null && ontoStack && (_world.Items.Get(to)?.Amount ?? 0) > targetAmount;
                    bool moved = merged || item != null && item.Container == to;

                    ReleaseHeldItem();

                    return Json
                    (
                        w =>
                        {
                            w.WriteStartObject();
                            w.WriteBoolean("moved", moved);

                            if (merged)
                            {
                                w.WriteBoolean("mergedIntoStack", true);
                            }

                            if (item != null)
                            {
                                w.WritePropertyName("item");
                                WriteItem(w, item);
                            }

                            WriteMessagesSince(w, before, 0);
                            w.WriteEndObject();
                        }
                    );
                }
            );
        }

        // picks an item up and puts it on; the server decides whether the hands are free
        private byte[] Equip(uint serial)
        {
            Rules rules = RequireRules();
            Layer layer = Layer.Invalid;

            long before = Lift
            (
                serial,
                rules,
                item =>
                {
                    if (!item.ItemData.IsWearable)
                    {
                        throw new BridgeException(403, "that can't be worn or held");
                    }

                    layer = (Layer)item.ItemData.Layer;
                },
                0
            );

            OnGame
            (
                () =>
                {
                    GameActions.Equip(_world);

                    return true;
                }
            );

            PaceFromNow();

            bool answered = WaitFor(() => _world.Items.Get(serial) != null, MOVE_TIMEOUT);
            Thread.Sleep(SETTLE_TIME);

            if (!answered && !OnGame(() => HasSystemMessageAfter(before)))
            {
                OnGame
                (
                    () =>
                    {
                        ReleaseHeldItem();

                        return true;
                    }
                );

                Halt($"no answer after equipping {Hex(serial)}");
            }

            return OnGame
            (
                () =>
                {
                    Item item = _world.Items.Get(serial);
                    bool equipped = item != null && item.Container == _world.Player.Serial && item.Layer == layer;

                    ReleaseHeldItem();

                    return Json
                    (
                        w =>
                        {
                            w.WriteStartObject();
                            w.WriteBoolean("equipped", equipped);

                            if (item != null)
                            {
                                w.WritePropertyName("item");
                                WriteItem(w, item);
                            }

                            WriteMessagesSince(w, before, 0);
                            w.WriteEndObject();
                        }
                    );
                }
            );
        }

        // uses an item held in the hands (such as a wand) on a target item
        private byte[] Use(uint serial, uint target)
        {
            Rules rules = RequireRules();
            long before = 0;
            bool targeting = false;

            for (int attempt = 0; attempt < 2 && !targeting; attempt++)
            {
                WaitForActionSlot();

                before = OnGame
                (
                    () =>
                    {
                        CheckNobodyElse(rules);
                        Item item = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such item nearby");

                        // nothing else is ever double-clicked, so a potion can't be drunk by mistake
                        if (item.Container != _world.Player.Serial || item.Layer != Layer.OneHanded && item.Layer != Layer.TwoHanded)
                        {
                            throw new BridgeException(403, "only an item in the character's hands can be used");
                        }

                        Item aim = _world.Items.Get(target) ?? throw new BridgeException(404, "no such target nearby");
                        CheckInReach(CheckReachable(aim, rules, "target"), TARGET_REACH);

                        if (_world.TargetManager.IsTargeting)
                        {
                            _world.TargetManager.CancelTarget();
                        }

                        GameActions.DoubleClick(_world, serial);

                        return _lastMessageId;
                    }
                );

                WaitFor(() => _world.TargetManager.IsTargeting || HasSystemMessageAfter(before), TARGET_TIMEOUT);
                targeting = OnGame(() => _world.TargetManager.IsTargeting);

                if (!targeting && !OnGame(() => SawMessage(before, MUST_WAIT)))
                {
                    break;
                }
            }

            if (!targeting && !OnGame(() => HasMessageAfter(before)))
            {
                Halt($"no answer when using {Hex(serial)}");
            }

            if (targeting)
            {
                long aimed = OnGame
                (
                    () =>
                    {
                        _world.TargetManager.Target(target);

                        return _lastMessageId;
                    }
                );

                if (WaitFor(() => HasMessageFrom(target, aimed) || HasSystemMessageAfter(aimed), USE_RESULT_TIMEOUT))
                {
                    Thread.Sleep(SETTLE_TIME);
                }
                else
                {
                    OnGame(CancelTarget);
                    Halt($"no answer after targeting {Hex(target)}");
                }
            }

            // never leave a cursor waiting for a click
            OnGame(CancelTarget);

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        w.WriteStartObject();
                        w.WriteBoolean("targeted", targeting);
                        WriteMessagesSince(w, before, 0);

                        Item t = _world.Items.Get(target);

                        if (t != null)
                        {
                            w.WritePropertyName("target");
                            WriteItem(w, t);
                        }

                        w.WriteEndObject();
                    }
                )
            );
        }

        // lifts an item after the checks pass, retrying once if the server asks to wait; returns the message id before the lift
        private long Lift(uint serial, Rules rules, Action<Item> check, int amount)
        {
            for (int attempt = 0; ; attempt++)
            {
                WaitForActionSlot();

                long before = OnGame
                (
                    () =>
                    {
                        CheckNobodyElse(rules);

                        if (Client.Game.UO.GameCursor.ItemHold.Enabled)
                        {
                            throw new BridgeException(409, "already holding an item");
                        }

                        Item item = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such item nearby");
                        CheckInReach(CheckReachable(item, rules, "pick up"), REACH);
                        check(item);

                        int lift = Math.Max(1, (int)item.Amount);

                        if (amount > 0 && amount < lift)
                        {
                            if (!item.ItemData.IsStackable)
                            {
                                throw new BridgeException(400, "only a stack can be split");
                            }

                            lift = amount;
                        }

                        if (!GameActions.PickUp(_world, serial, 0, 0, lift))
                        {
                            throw new BridgeException(409, "the client would not pick it up (too far away?)");
                        }

                        return _lastMessageId;
                    }
                );

                Thread.Sleep(LIFT_WAIT);

                (bool held, bool mustWait) = OnGame
                (
                    () => (Client.Game.UO.GameCursor.ItemHold.Enabled && Client.Game.UO.GameCursor.ItemHold.Serial == serial, SawMessage(before, MUST_WAIT))
                );

                if (held)
                {
                    return before;
                }

                if (!mustWait || attempt > 0)
                {
                    string why = OnGame(() => LastMessageText(before));

                    if (why == null)
                    {
                        Halt($"no answer when picking up {Hex(serial)}");
                    }

                    throw new BridgeException(409, $"could not pick it up: {why}");
                }
            }
        }

        // drops anything the agent is still holding back into the backpack
        private void ReleaseHeldItem()
        {
            ItemHold hold = Client.Game.UO.GameCursor.ItemHold;
            Item backpack = _world.Player.FindItemByLayer(Layer.Backpack);

            if (hold.Enabled && backpack != null)
            {
                GameActions.DropItem(hold.Serial, 0xFFFF, 0xFFFF, 0, backpack.Serial);
            }
        }

        private bool CloseContainer(uint serial)
        {
            ContainerGump gump = UIManager.GetGump<ContainerGump>(serial);
            gump?.Dispose();

            return gump != null;
        }

        private bool CancelTarget()
        {
            bool targeting = _world.TargetManager.IsTargeting;

            if (targeting)
            {
                _world.TargetManager.CancelTarget();
            }

            return targeting;
        }

        // ---- rules, on the game thread unless noted ----

        // returns the item's outermost container on the ground, or null when the character carries it
        private Item CheckReachable(Item item, Rules rules, string what)
        {
            if (rules.NeverTouch.Contains(item.Graphic))
            {
                throw new BridgeException(403, $"the agent may never {what} that kind of item");
            }

            Item current = item;

            while (true)
            {
                if (rules.OffLimits.Contains(current.Serial))
                {
                    throw new BridgeException(403, "that is in an off-limits container");
                }

                if (current.OnGround)
                {
                    if (!rules.Contains(_world.MapIndex, current.X, current.Y, current.Z))
                    {
                        throw new BridgeException(403, "that is outside the agent's area");
                    }

                    return current;
                }

                if (current.Container == _world.Player.Serial)
                {
                    return null;
                }

                Entity parent = _world.Get(current.Container);

                if (parent is Item container)
                {
                    current = container;
                }
                else
                {
                    throw new BridgeException(403, parent == null ? "can't tell where that is" : "that belongs to someone else");
                }
            }
        }

        private void CheckDropTarget(Item item, Item target, Rules rules, bool checkReach = true)
        {
            if (target == null)
            {
                throw new BridgeException(404, "no such container nearby");
            }

            if (target.Serial == item.Serial)
            {
                throw new BridgeException(400, "can't drop an item into itself");
            }

            bool stack = target.Graphic == item.Graphic && target.Hue == item.Hue && target.ItemData.IsStackable;

            if (!target.ItemData.IsContainer && !stack)
            {
                throw new BridgeException(403, "items can only go into containers or onto a stack of the same kind");
            }

            Item root = CheckReachable(target, rules, "drop onto");

            if (checkReach)
            {
                CheckInReach(root, REACH);
            }
        }

        // the outermost container on the ground, or null when the character carries it (or it can't be told)
        private Item GroundRoot(Item item)
        {
            for (Item current = item; current != null; current = _world.Get(current.Container) as Item)
            {
                if (current.OnGround)
                {
                    return current;
                }
            }

            return null;
        }

        private void CheckInReach(Item root, int reach)
        {
            if (root == null)
            {
                return;
            }

            int distance = Math.Max(Math.Abs(root.X - _world.Player.X), Math.Abs(root.Y - _world.Player.Y));

            if (distance > reach)
            {
                throw new BridgeException(409, $"too far away ({distance} tiles, reach is {reach}); walk closer first");
            }
        }

        private void CheckNobodyElse(Rules rules)
        {
            foreach (Mobile m in _world.Mobiles.Values)
            {
                if (m == _world.Player || m.IsDestroyed || !(m.IsHuman || m.IsDead) || rules.IgnorePeople.Contains(m.Name ?? ""))
                {
                    continue;
                }

                if (rules.Contains(_world.MapIndex, m.X, m.Y, m.Z))
                {
                    throw new BridgeException(409, $"paused: {(string.IsNullOrEmpty(m.Name) ? "someone" : m.Name)} is in the agent's area");
                }
            }
        }

        // on the listener thread; reloads Agent/rules.json when it changes
        private Rules RequireRules()
        {
            string path = Path.Combine(CUOEnviroment.ExecutablePath, "Agent", "rules.json");

            if (!File.Exists(path))
            {
                throw new BridgeException(403, "actions are off until Agent/rules.json sets the agent's area");
            }

            DateTime time = File.GetLastWriteTimeUtc(path);

            if (_rules == null || time != _rulesTime)
            {
                try
                {
                    _rules = Rules.Parse(File.ReadAllBytes(path));
                    _rulesTime = time;
                }
                catch (Exception ex)
                {
                    _rules = null;

                    throw new BridgeException(403, $"Agent/rules.json is not valid: {ex.Message}");
                }
            }

            return _rules;
        }

        // on the listener thread: waits for this action's turn, then books the gap before the next one
        private void WaitForActionSlot()
        {
            CheckNotHalted();

            int wait = (int)(_nextAction - DateTime.UtcNow).TotalMilliseconds;

            if (wait > 0)
            {
                Thread.Sleep(wait);
            }

            Rules pacing = TryRules() ?? Rules.Defaults;
            bool takeBreak = ++_burstCount >= pacing.Burst;

            if (takeBreak)
            {
                _burstCount = 0;
            }

            int gap = takeBreak ? _random.Next(pacing.BreakMin, pacing.BreakMax + 1) : _random.Next(pacing.GapMin, pacing.GapMax + 1);
            _nextAction = DateTime.UtcNow.AddMilliseconds(gap);
        }

        // on the listener thread: the next action waits a full gap from now
        private void PaceFromNow()
        {
            Rules pacing = TryRules() ?? Rules.Defaults;
            DateTime next = DateTime.UtcNow.AddMilliseconds(_random.Next(pacing.GapMin, pacing.GapMax + 1));

            if (next > _nextAction)
            {
                _nextAction = next;
            }
        }

        // on the listener thread
        private void CheckNotHalted()
        {
            if (_halted != null)
            {
                throw new BridgeException(423, $"stopped because the server went quiet ({_halted}); check the game, then resume");
            }
        }

        // on the listener thread: the server didn't answer, so stop everything until told to resume
        private void Halt(string why)
        {
            _halted = $"{why} at {DateTime.Now:HH:mm:ss}";
            Log.Warn($"Agent bridge stopped: {_halted}");

            throw new BridgeException(423, $"stopped because the server went quiet ({_halted}); check the game, then resume");
        }

        // on the listener thread; like RequireRules, but missing or broken rules give null
        private Rules TryRules()
        {
            try
            {
                return RequireRules();
            }
            catch (BridgeException)
            {
                return null;
            }
        }

        private bool SawMessage(long after, string text)
        {
            foreach (Message m in _messages)
            {
                if (m.Id > after && m.Text.Contains(text, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        // messages from the server itself, not said by or about anything in the world
        private bool HasSystemMessageAfter(long after)
        {
            foreach (Message m in _messages)
            {
                if (m.Id > after && m.Serial == 0)
                {
                    return true;
                }
            }

            return false;
        }

        private string LastMessageText(long after)
        {
            string text = null;

            foreach (Message m in _messages)
            {
                if (m.Id > after)
                {
                    text = m.Text;
                }
            }

            return text;
        }

        private bool HasMessageAfter(long after) => _lastMessageId > after;

        private bool ContainerAnswered(uint serial, long after) => _containerAnswers.TryGetValue(serial, out long at) && at > after;

        private bool HasMessageFrom(uint serial, long after)
        {
            foreach (Message m in _messages)
            {
                if (m.Id > after && m.Serial == serial)
                {
                    return true;
                }
            }

            return false;
        }

        private bool WaitFor(Func<bool> condition, int timeout)
        {
            DateTime end = DateTime.UtcNow.AddMilliseconds(timeout);

            while (true)
            {
                if (OnGame(condition))
                {
                    return true;
                }

                if (DateTime.UtcNow >= end)
                {
                    return false;
                }

                Thread.Sleep(POLL_INTERVAL);
            }
        }

        private T OnGame<T>(Func<T> func)
        {
            T result = default;
            Exception error = null;

            // not disposed: the game thread may still set it after a timeout
            var done = new ManualResetEventSlim();

            _work.Enqueue
            (
                () =>
                {
                    try
                    {
                        if (_world.Player == null)
                        {
                            throw new BridgeException(503, "not in the game");
                        }

                        result = func();
                    }
                    catch (Exception ex)
                    {
                        error = ex;
                    }
                    finally
                    {
                        done.Set();
                    }
                }
            );

            if (!done.Wait(GAME_THREAD_TIMEOUT))
            {
                throw new BridgeException(503, "the game is not responding (logged out?)");
            }

            if (error is BridgeException)
            {
                throw error;
            }

            if (error != null)
            {
                Log.Error($"Agent bridge: {error}");

                throw new BridgeException(500, error.Message);
            }

            return result;
        }

        // ---- json, on the game thread ----

        private void WriteStatus(Utf8JsonWriter w, string halted)
        {
            PlayerMobile p = _world.Player;

            w.WriteStartObject();
            w.WriteNumber("bridge", VERSION);

            if (halted != null)
            {
                w.WriteString("halted", halted);
            }

            w.WriteString("character", ProfileManager.CurrentProfile?.CharacterName ?? p.Name);
            w.WriteString("serial", Hex(p.Serial));
            w.WriteNumber("map", _world.MapIndex);
            w.WriteNumber("x", p.X);
            w.WriteNumber("y", p.Y);
            w.WriteNumber("z", p.Z);
            w.WriteNumber("hits", p.Hits);
            w.WriteNumber("hitsMax", p.HitsMax);
            w.WriteNumber("stamina", p.Stamina);
            w.WriteNumber("staminaMax", p.StaminaMax);
            w.WriteNumber("mana", p.Mana);
            w.WriteNumber("manaMax", p.ManaMax);
            w.WriteNumber("weight", p.Weight);
            w.WriteNumber("weightMax", p.WeightMax);
            w.WriteBoolean("warMode", p.InWarMode);
            w.WriteBoolean("hidden", p.IsHidden);
            w.WriteBoolean("dead", p.IsDead);
            w.WriteBoolean("targeting", _world.TargetManager.IsTargeting);

            ItemHold hold = Client.Game.UO.GameCursor.ItemHold;

            if (hold.Enabled)
            {
                w.WriteString("holding", Hex(hold.Serial));
            }
            else
            {
                w.WriteNull("holding");
            }

            Item backpack = p.FindItemByLayer(Layer.Backpack);

            if (backpack != null)
            {
                w.WritePropertyName("backpack");
                WriteItem(w, backpack);
            }

            w.WriteStartArray("hands");

            foreach (Layer layer in new[] { Layer.OneHanded, Layer.TwoHanded })
            {
                Item held = p.FindItemByLayer(layer);

                if (held != null)
                {
                    WriteItem(w, held);
                }
            }

            w.WriteEndArray();
            w.WriteNumber("lastMessageId", _lastMessageId);
            w.WriteEndObject();
        }

        private void WriteNearby(Utf8JsonWriter w, int range, bool containersOnly)
        {
            PlayerMobile p = _world.Player;
            var items = new List<Item>();
            var mobiles = new List<Mobile>();

            foreach (Item item in _world.Items.Values)
            {
                if (item.OnGround && !item.IsMulti && !item.IsDestroyed && item.Distance <= range && (!containersOnly || item.ItemData.IsContainer))
                {
                    items.Add(item);
                }
            }

            foreach (Mobile mobile in _world.Mobiles.Values)
            {
                if (mobile != p && !mobile.IsDestroyed && mobile.Distance <= range)
                {
                    mobiles.Add(mobile);
                }
            }

            items.Sort((a, b) => a.Distance.CompareTo(b.Distance));
            mobiles.Sort((a, b) => a.Distance.CompareTo(b.Distance));

            w.WriteStartObject();
            w.WriteStartObject("you");
            w.WriteNumber("x", p.X);
            w.WriteNumber("y", p.Y);
            w.WriteNumber("z", p.Z);
            w.WriteEndObject();
            w.WriteStartArray("items");

            foreach (Item item in items)
            {
                WriteItem(w, item);
            }

            w.WriteEndArray();
            w.WriteStartArray("mobiles");

            foreach (Mobile mobile in mobiles)
            {
                w.WriteStartObject();
                w.WriteString("serial", Hex(mobile.Serial));
                w.WriteString("name", mobile.Name);
                w.WriteString("body", Hex(mobile.Graphic));
                w.WriteNumber("hue", mobile.Hue);
                WritePosition(w, mobile);
                w.WriteString("notoriety", mobile.NotorietyFlag.ToString());
                w.WriteBoolean("human", mobile.IsHuman);
                w.WriteBoolean("yourPet", mobile.IsRenamable);
                w.WriteBoolean("dead", mobile.IsDead);
                w.WriteBoolean("hidden", mobile.IsHidden);
                w.WriteEndObject();
            }

            w.WriteEndArray();
            w.WriteEndObject();
        }

        private void WriteItemDetails(Utf8JsonWriter w, uint serial)
        {
            Item item = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such item nearby");

            w.WriteStartObject();
            w.WritePropertyName("item");
            WriteItem(w, item);
            w.WriteStartArray("insideOf");

            // the chain of containers up to the ground or the character carrying it
            for (uint parent = item.Container; SerialHelper.IsValid(parent);)
            {
                Entity e = _world.Get(parent);

                if (e == null)
                {
                    w.WriteStartObject();
                    w.WriteString("serial", Hex(parent));
                    w.WriteBoolean("unknown", true);
                    w.WriteEndObject();

                    break;
                }

                if (e is Item container)
                {
                    WriteItem(w, container);
                    parent = container.Container;
                }
                else
                {
                    w.WriteStartObject();
                    w.WriteString("serial", Hex(e.Serial));
                    w.WriteString("mobile", e.Name);
                    w.WriteEndObject();

                    break;
                }
            }

            w.WriteEndArray();
            w.WriteEndObject();
        }

        private void WriteContents(Utf8JsonWriter w, uint serial, int depth, int level)
        {
            Item container = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such item nearby");

            if (level == 0)
            {
                w.WriteStartObject();
                w.WritePropertyName("container");
                WriteItem(w, container);
                RememberContainerGump(serial);

                // where items can sit in the container's window: an item at (x, y) is drawn with its art's
                // top left corner there, and must fit inside this area
                if (_containerGumps.TryGetValue(serial, out ushort gump))
                {
                    Rectangle area = _world.ContainerManager.Get(gump).Bounds;

                    w.WriteString("gump", Hex(gump));
                    w.WriteStartArray("area");
                    w.WriteNumberValue(area.X);
                    w.WriteNumberValue(area.Y);
                    w.WriteNumberValue(area.Width);
                    w.WriteNumberValue(area.Height);
                    w.WriteEndArray();
                }

                w.WriteStartArray("items");
            }

            for (LinkedObject i = container.Items; i != null; i = i.Next)
            {
                Item child = (Item)i;

                if (child.Layer != Layer.Invalid)
                {
                    continue; // worn, not inside
                }

                w.WriteStartObject();
                WriteItemFields(w, child);

                if (child.ItemData.IsContainer && level + 1 < depth)
                {
                    w.WriteStartArray("items");
                    WriteContents(w, child.Serial, depth, level + 1);
                    w.WriteEndArray();
                }

                w.WriteEndObject();
            }

            if (level == 0)
            {
                w.WriteEndArray();
                w.WriteEndObject();
            }
        }

        private static void WriteDone(Utf8JsonWriter w, bool done)
        {
            w.WriteStartObject();
            w.WriteBoolean("done", done);
            w.WriteEndObject();
        }

        private void RememberContainerGump(uint serial)
        {
            ContainerGump gump = UIManager.GetGump<ContainerGump>(serial);

            if (gump != null)
            {
                _containerGumps[serial] = gump.Graphic;
            }
        }

        private void WriteMessages(Utf8JsonWriter w, long after)
        {
            w.WriteStartObject();
            w.WriteNumber("lastMessageId", _lastMessageId);
            WriteMessagesSince(w, after, 0);
            w.WriteEndObject();
        }

        private void WriteMessagesSince(Utf8JsonWriter w, long after, uint onlySerial)
        {
            w.WriteStartArray("messages");

            foreach (Message m in _messages)
            {
                if (m.Id <= after || (onlySerial != 0 && m.Serial != onlySerial))
                {
                    continue;
                }

                w.WriteStartObject();
                w.WriteNumber("id", m.Id);
                w.WriteString("time", m.Time.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture));
                w.WriteString("type", m.Type.ToString());

                if (m.Serial != 0)
                {
                    w.WriteString("serial", Hex(m.Serial));
                }

                if (!string.IsNullOrEmpty(m.Name))
                {
                    w.WriteString("name", m.Name);
                }

                w.WriteString("text", m.Text);
                w.WriteEndObject();
            }

            w.WriteEndArray();
        }

        private void WriteItem(Utf8JsonWriter w, Item item)
        {
            w.WriteStartObject();
            WriteItemFields(w, item);
            w.WriteEndObject();
        }

        private void WriteItemFields(Utf8JsonWriter w, Item item)
        {
            w.WriteString("serial", Hex(item.Serial));
            w.WriteString("graphic", Hex(item.Graphic));
            w.WriteNumber("hue", item.Hue);
            w.WriteString("type", StringHelper.GetPluralAdjustedString(item.ItemData.Name ?? "", item.Amount > 1).Trim());

            if (item.Amount > 1)
            {
                w.WriteNumber("amount", item.Amount);
            }

            if (_labels.TryGetValue(item.Serial, out Label label))
            {
                w.WriteString("name", string.Join(" / ", label.Lines));
            }

            if (item.OnGround)
            {
                WritePosition(w, item);
            }
            else
            {
                // position inside the container's gump
                w.WriteNumber("x", item.X);
                w.WriteNumber("y", item.Y);
            }

            if (item.Layer != Layer.Invalid)
            {
                w.WriteString("layer", item.Layer.ToString());
            }

            // size of the item's picture in a container window, and the part of it that isn't transparent
            ref readonly var art = ref Client.Game.UO.Arts.GetArt(item.DisplayedGraphic);

            if (art.Texture != null)
            {
                Rectangle visible = Client.Game.UO.Arts.GetRealArtBounds(item.DisplayedGraphic);

                w.WriteStartObject("art");
                w.WriteNumber("w", art.UV.Width);
                w.WriteNumber("h", art.UV.Height);
                w.WriteStartArray("visible");
                w.WriteNumberValue(visible.X);
                w.WriteNumberValue(visible.Y);
                w.WriteNumberValue(visible.Width);
                w.WriteNumberValue(visible.Height);
                w.WriteEndArray();
                w.WriteEndObject();
            }

            if (item.ItemData.IsContainer)
            {
                int count = 0;

                for (LinkedObject i = item.Items; i != null; i = i.Next)
                {
                    count++;
                }

                w.WriteBoolean("container", true);
                w.WriteBoolean("open", item.Opened);
                w.WriteNumber("knownItems", count);
            }
        }

        private void WritePosition(Utf8JsonWriter w, GameObject o)
        {
            w.WriteNumber("x", o.X);
            w.WriteNumber("y", o.Y);
            w.WriteNumber("z", o.Z);
            w.WriteNumber("dx", o.X - _world.Player.X);
            w.WriteNumber("dy", o.Y - _world.Player.Y);
            w.WriteNumber("distance", o.Distance);
        }

        // ---- helpers ----

        private static byte[] Json(Action<Utf8JsonWriter> write)
        {
            var buffer = new ArrayBufferWriter<byte>();

            using (var writer = new Utf8JsonWriter(buffer, new JsonWriterOptions { Indented = true }))
            {
                write(writer);
            }

            return buffer.WrittenSpan.ToArray();
        }

        private static byte[] Error(string message)
        {
            return Json
            (
                w =>
                {
                    w.WriteStartObject();
                    w.WriteString("error", message);
                    w.WriteEndObject();
                }
            );
        }

        private static string ReadHead(NetworkStream stream)
        {
            byte[] buffer = new byte[MAX_HEADER_BYTES];
            int length = 0;

            while (length < buffer.Length)
            {
                int read = stream.Read(buffer, length, buffer.Length - length);

                if (read <= 0)
                {
                    return null;
                }

                length += read;

                // requests carry no body, so the end of the headers is the end of the request
                int end = buffer.AsSpan(0, length).IndexOf("\r\n\r\n"u8);

                if (end >= 0)
                {
                    return Encoding.ASCII.GetString(buffer, 0, end);
                }
            }

            return null;
        }

        private static void Respond(NetworkStream stream, int status, byte[] body)
        {
            string reason = status switch
            {
                200 => "OK",
                400 => "Bad Request",
                401 => "Unauthorized",
                403 => "Forbidden",
                404 => "Not Found",
                405 => "Method Not Allowed",
                409 => "Conflict",
                423 => "Locked",
                503 => "Service Unavailable",
                _ => "Error"
            };

            byte[] head = Encoding.ASCII.GetBytes
            (
                $"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {body.Length}\r\nConnection: close\r\n\r\n"
            );

            stream.Write(head, 0, head.Length);
            stream.Write(body, 0, body.Length);
        }

        private static bool IsAuthorized(string authorization, byte[] token)
        {
            const string PREFIX = "Bearer ";

            if (authorization == null || !authorization.StartsWith(PREFIX, StringComparison.Ordinal))
            {
                return false;
            }

            byte[] given = Encoding.ASCII.GetBytes(authorization.Substring(PREFIX.Length).Trim().ToUpperInvariant());

            return CryptographicOperations.FixedTimeEquals(given, token);
        }

        private static Dictionary<string, string> ParseQuery(string query)
        {
            var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

            foreach (string pair in query.Split('&', StringSplitOptions.RemoveEmptyEntries))
            {
                int eq = pair.IndexOf('=');
                string key = Uri.UnescapeDataString(eq < 0 ? pair : pair.Substring(0, eq));
                string value = eq < 0 ? "" : Uri.UnescapeDataString(pair.Substring(eq + 1).Replace('+', ' '));
                result[key] = value;
            }

            return result;
        }

        private static void RequireMethod(string method, string expected)
        {
            if (method != expected)
            {
                throw new BridgeException(405, $"use {expected}");
            }
        }

        private static uint GetSerial(Dictionary<string, string> query, string key = "serial")
        {
            if (!query.TryGetValue(key, out string text) || !TryParseSerial(text, out uint serial))
            {
                throw new BridgeException(400, $"{key} missing or not a number");
            }

            return serial;
        }

        private static int GetRequiredInt(Dictionary<string, string> query, string key)
        {
            if (!query.TryGetValue(key, out string text) || !int.TryParse(text, out int value))
            {
                throw new BridgeException(400, $"{key} missing or not a number");
            }

            return value;
        }

        private static List<uint> GetSerials(Dictionary<string, string> query)
        {
            var serials = new List<uint>();

            if (query.TryGetValue("serial", out string text))
            {
                foreach (string part in text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
                {
                    if (!TryParseSerial(part, out uint serial))
                    {
                        throw new BridgeException(400, $"not a serial: {part}");
                    }

                    serials.Add(serial);
                }
            }

            if (serials.Count == 0)
            {
                throw new BridgeException(400, "serial missing");
            }

            return serials;
        }

        private static bool TryParseSerial(string text, out uint serial)
        {
            text = text.Trim();

            if (text.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
            {
                return uint.TryParse(text.AsSpan(2), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out serial);
            }

            return uint.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out serial);
        }

        private static int GetInt(Dictionary<string, string> query, string key, int fallback)
        {
            return query.TryGetValue(key, out string text) && int.TryParse(text, out int value) ? value : fallback;
        }

        private static long GetLong(Dictionary<string, string> query, string key, long fallback)
        {
            return query.TryGetValue(key, out string text) && long.TryParse(text, out long value) ? value : fallback;
        }

        private static string Hex(uint value) => "0x" + value.ToString("X8", CultureInfo.InvariantCulture);

        private static string Hex(ushort value) => "0x" + value.ToString("X4", CultureInfo.InvariantCulture);

        private sealed class Message
        {
            public long Id;
            public DateTime Time;
            public uint Serial;
            public string Name;
            public MessageType Type;
            public string Text;
        }

        private sealed class Rules
        {
            public int Map = -1;
            public int X1, Y1, X2, Y2;
            public int ZMin = sbyte.MinValue, ZMax = sbyte.MaxValue;
            public readonly HashSet<uint> OffLimits = new HashSet<uint>();
            public readonly HashSet<ushort> NeverTouch = new HashSet<ushort>();
            public readonly HashSet<string> IgnorePeople = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            // a random gap between actions, and a longer break after every Burst actions (milliseconds)
            public int GapMin = 1200, GapMax = 2000, Burst = 5, BreakMin = 3000, BreakMax = 5000;

            public static readonly Rules Defaults = new Rules();

            public bool Contains(int map, int x, int y, int z)
            {
                return (Map < 0 || map == Map) && x >= X1 && x <= X2 && y >= Y1 && y <= Y2 && z >= ZMin && z <= ZMax;
            }

            // { "map": 0, "area": [x1, y1, x2, y2], "z": [min, max], "offLimits": ["0x..."], "neverTouch": ["0x1766"], "ignorePeople": [] }
            public static Rules Parse(byte[] json)
            {
                using JsonDocument doc = JsonDocument.Parse
                (
                    json,
                    new JsonDocumentOptions { AllowTrailingCommas = true, CommentHandling = JsonCommentHandling.Skip }
                );

                JsonElement root = doc.RootElement;
                var rules = new Rules();
                JsonElement area = root.GetProperty("area");

                if (area.GetArrayLength() != 4)
                {
                    throw new FormatException("area needs four numbers: x1, y1, x2, y2");
                }

                rules.X1 = Math.Min(area[0].GetInt32(), area[2].GetInt32());
                rules.X2 = Math.Max(area[0].GetInt32(), area[2].GetInt32());
                rules.Y1 = Math.Min(area[1].GetInt32(), area[3].GetInt32());
                rules.Y2 = Math.Max(area[1].GetInt32(), area[3].GetInt32());

                if (root.TryGetProperty("map", out JsonElement map))
                {
                    rules.Map = map.GetInt32();
                }

                if (root.TryGetProperty("z", out JsonElement z))
                {
                    rules.ZMin = z[0].GetInt32();
                    rules.ZMax = z[1].GetInt32();
                }

                if (root.TryGetProperty("offLimits", out JsonElement offLimits))
                {
                    foreach (JsonElement e in offLimits.EnumerateArray())
                    {
                        rules.OffLimits.Add(ParseNumber(e.GetString()));
                    }
                }

                if (root.TryGetProperty("neverTouch", out JsonElement neverTouch))
                {
                    foreach (JsonElement e in neverTouch.EnumerateArray())
                    {
                        rules.NeverTouch.Add((ushort)ParseNumber(e.GetString()));
                    }
                }

                // "pacing": { "gap": [1200, 2000], "burst": 5, "break": [3000, 5000] }; never faster than the server allows
                if (root.TryGetProperty("pacing", out JsonElement pacing))
                {
                    if (pacing.TryGetProperty("gap", out JsonElement gap))
                    {
                        rules.GapMin = Math.Max(1100, gap[0].GetInt32());
                        rules.GapMax = Math.Max(rules.GapMin, gap[1].GetInt32());
                    }

                    if (pacing.TryGetProperty("burst", out JsonElement burst))
                    {
                        rules.Burst = Math.Max(1, burst.GetInt32());
                    }

                    if (pacing.TryGetProperty("break", out JsonElement pause))
                    {
                        rules.BreakMin = Math.Max(rules.GapMin, pause[0].GetInt32());
                        rules.BreakMax = Math.Max(rules.BreakMin, pause[1].GetInt32());
                    }
                }

                if (root.TryGetProperty("ignorePeople", out JsonElement people))
                {
                    foreach (JsonElement e in people.EnumerateArray())
                    {
                        rules.IgnorePeople.Add(e.GetString());
                    }
                }

                return rules;
            }

            public void Write(Utf8JsonWriter w)
            {
                w.WriteStartObject();
                w.WriteNumber("map", Map);
                w.WriteStartArray("area");
                w.WriteNumberValue(X1);
                w.WriteNumberValue(Y1);
                w.WriteNumberValue(X2);
                w.WriteNumberValue(Y2);
                w.WriteEndArray();
                w.WriteStartArray("z");
                w.WriteNumberValue(ZMin);
                w.WriteNumberValue(ZMax);
                w.WriteEndArray();
                w.WriteStartArray("offLimits");

                foreach (uint serial in OffLimits)
                {
                    w.WriteStringValue(Hex(serial));
                }

                w.WriteEndArray();
                w.WriteStartArray("neverTouch");

                foreach (ushort graphic in NeverTouch)
                {
                    w.WriteStringValue(Hex(graphic));
                }

                w.WriteEndArray();
                w.WriteStartArray("ignorePeople");

                foreach (string name in IgnorePeople)
                {
                    w.WriteStringValue(name);
                }

                w.WriteEndArray();
                w.WriteStartObject("pacing");
                w.WriteStartArray("gap");
                w.WriteNumberValue(GapMin);
                w.WriteNumberValue(GapMax);
                w.WriteEndArray();
                w.WriteNumber("burst", Burst);
                w.WriteStartArray("break");
                w.WriteNumberValue(BreakMin);
                w.WriteNumberValue(BreakMax);
                w.WriteEndArray();
                w.WriteEndObject();
                w.WriteEndObject();
            }

            private static uint ParseNumber(string text)
            {
                if (text == null || !TryParseSerial(text, out uint value))
                {
                    throw new FormatException($"not a number: {text}");
                }

                return value;
            }
        }

        private sealed class Label
        {
            public readonly List<string> Lines = new List<string>();
            public DateTime Time;
        }

        private sealed class BridgeException : Exception
        {
            public BridgeException(int status, string message) : base(message) => Status = status;

            public int Status { get; }
        }
    }
}
