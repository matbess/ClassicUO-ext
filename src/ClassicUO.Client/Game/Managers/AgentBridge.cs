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
    // A character can have its own Agent/rules-<character>.json (several areas, partners it may trade
    // with, words it may say, spells and skills it may use, mounts it may ride). Its "guard" goes off the
    // moment someone talks nearby, loiters next to it, attacks it, opens a trade or takes a watched item:
    // work stops (only getting away and hiding are allowed) and Agent/alarm.json tells the partner's client.
    internal sealed partial class AgentBridge
    {
        private const int FIRST_PORT = 7780;
        private const int LAST_PORT = 7789;
        private const int VERSION = 10; // 3: /skill takes a target (Animal Taming on the character's own horse); 4: no staff alarm (the user, 2026-11-04: staff get the normal guard); 5: a walk that starts outside the area may go back in; 6: menus, gumps, target cursor, skills and the event log (AgentBridgeDialogs.cs); 7: fights (creatures' health, skills and spells aimed at creatures, running walks that don't wait, doors and keys; the user takes over by giving a command of their own); 8: /cast wait=0 answers at once and the bridge aims the spell's cursor itself when it comes, so the agent keeps moving and looking while the spell goes off, and reads the outcome from the messages (the user, 2026-11-06: "Cast .. then do all the other normal stuff and when a result from the spell shows up result=success/fail"); cursor=0 for a spell with no target (Magic Reflection); 9: /use wait=0 double-clicks and answers at once (a trapped pouch to break paralysis goes off without a word, and waiting for one stopped the bridge); 10: bandages: "useOnGround" kinds are double-clicked where they lie (the pile of bandages on the tower floor) and /use aims at a "patients" character (Isabel's ghost, to train Healing; the user, 2026-11-08)
        private const int GUARD_INTERVAL = 250;  // milliseconds between the guard's checks
        private const int ALARM_FILE_INTERVAL = 1000;
        private const int CAST_TIMEOUT = 6000;   // from casting to the target cursor
        private const int NO_CURSOR_TIMEOUT = 1500; // a spell with no cursor: from casting to his words
        private const int LAND_RESULT_TIMEOUT = 6000; // mining and smelting answer after the swing
        private const int RECALL_TIMEOUT = 6000;
        private const int TRADE_TIMEOUT = 3000;
        private const int MAX_TILE_RANGE = 8;
        private const int ANIMATION_LOG = 400;
        private const int SKILL_TIMEOUT = 3000;
        private const int MOUNT_TIMEOUT = 3000;
        private const int HIDING = 21;
        private const int REPEAT_WINDOW = 15000; // a stroke counts as a repeat within this long of the last one
        private const int TRAVEL_TIMEOUT = 180000;  // the longest ride /travel will make
        private const int TRAVEL_STUCK = 6000;      // no progress for this long ends a ride
        private const int TRAVEL_HANDOVER = 3;      // tiles before a stretch's end where the next one starts
        private const int STEPS_BACK_IN = 4;        // steps a walk that starts outside the area may take outside it
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
        private const int FIGHT_RANGE = 12;   // a creature a skill or spell is aimed at (provoking, a bolt) is at most this far
        private const int FIGHT_ANSWER = 2000; // in a fight, how long to wait for the server's word on an aim; never a halt
        private const int LIFT_WAIT = 1000; // between picking up and dropping: this server holds a drop that comes sooner and carries it out late
        private const int SAVE_LIMIT = 5;   // minutes: a world save that never says it's complete stops holding actions after this
        private const int ACTION_LOG = 300;
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
        private bool _saving; // the server is in a world save: it answers nothing until "world save complete"
        private DateTime _saveStarted;
        private TcpListener _listener;
        private string _infoPath;
        private uint _playerSerial;
        private uint _failedSerial;
        private string _characterName; // set on the game thread at start; read by the listener for the rules file

        // the guard, on the game thread
        private bool _guardOn;
        private DateTime _guardSince; // UTC; alarms written before this are old news
        private DateTime _nextGuardCheck;
        private DateTime _nextAlarmFileCheck;
        private int _lastHits = -1;
        private readonly Dictionary<uint, DateTime> _nearSince = new Dictionary<uint, DateTime>();
        private readonly HashSet<uint> _seenCarried = new HashSet<uint>();
        private volatile string _alarm; // the listener refuses normal work while it's set
        private DateTime _alarmAt;
        private DateTime _nextAutoHide;
        private DateTime _alarmFileSeen;
        private volatile bool _evading; // the agent is getting the character away (walking, hiding, recalling)
        private Threat _threat;
        private string _lastLogged;
        private volatile string _logoutRequest; // read by GameScene, which logs out at a safe point in its update

        // NPCs tell themselves apart by fidgeting (the user, 2026-11-02: an idle twist players never do, which the
        // server sends as an animation): recent animations, for learning which ones those are, and the characters
        // seen fidgeting, kept in Agent/npcs-learned.json
        private readonly Queue<(DateTime Time, uint Serial, string Name, ushort Action, int X, int Y)> _animations = new Queue<(DateTime, uint, string, ushort, int, int)>();
        private readonly HashSet<uint> _npcLearned = new HashSet<uint>();
        private bool _npcLoaded;

        // only touched on the listener thread
        private readonly Random _random = new Random();
        private DateTime _nextAction;
        private int _burstCount;
        private string _lastKind; // what the last action was, to tell a repeated stroke from a new action
        private DateTime _lastKindAt;
        private string _halted;
        private readonly Queue<(DateTime Time, string What, uint Serial)> _actions = new Queue<(DateTime, string, uint)>();
        private volatile Rules _rules; // the guard reads it on the game thread
        private DateTime _rulesTime;
        private string _rulesName;

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
                _inWork = true;

                try
                {
                    action();
                }
                finally
                {
                    _inWork = false;
                }
            }

            // the user gave a command of their own while the rules hand the character over to them: no more actions
            // until /resume (what happens next is theirs)
            string acted = _userActed;

            if (acted != null)
            {
                _userActed = null;

                if (_takenOver == null)
                {
                    _takenOver = $"{acted} at {DateTime.Now:HH:mm:ss}";
                    Log.Warn($"Agent bridge: the user took over ({_takenOver})");

                    if (_world.Player != null && _world.Player.Pathfinder.AutoWalking)
                    {
                        _world.Player.Pathfinder.StopAutoWalk();
                    }
                }
            }

            if (_aimTarget != 0)
            {
                // the bridge's own target, not the user's: outside _inWork the hand-over check took the aimed
                // Greater Heal for the user taking over and stopped the fight next to a gargoyle (2026-11-06 18:33:35)
                _inWork = true;

                try
                {
                    AimPending();
                }
                finally
                {
                    _inWork = false;
                }
            }

            if (_listener != null)
            {
                TakeSent();
            }

            if (_listener != null && _guardOn && _logoutRequest == null)
            {
                _inWork = true;

                try
                {
                    GuardTick();
                }
                finally
                {
                    _inWork = false;
                }
            }
        }

        // called by GameScene once per update, at the point where it can safely leave the game
        public string TakeLogoutRequest()
        {
            string why = _logoutRequest;
            _logoutRequest = null;

            return why;
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

                case 0x7C: // a menu (AgentBridgeDialogs.cs)
                    OnMenuPacket(data);

                    break;

                case 0x6C: // the server wants a target
                    OnTargetPacket(data);

                    break;

                case 0x3A: // a skill changed
                    OnSkillPacket(data);

                    break;

                case 0x6E when data.Length >= 7: // character animation: serial, action
                    NoteAnimation(BinaryPrimitives.ReadUInt32BigEndian(data.Slice(1)), BinaryPrimitives.ReadUInt16BigEndian(data.Slice(5)));

                    break;

                case 0xE2 when data.Length >= 9: // the newer animation packet: serial, type, action
                    NoteAnimation(BinaryPrimitives.ReadUInt32BigEndian(data.Slice(1)), BinaryPrimitives.ReadUInt16BigEndian(data.Slice(7)));

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
            _guardOn = false;
            _nearSince.Clear();
            _seenCarried.Clear();
            _alarm = null;
            _threat = null;

            if (_sending == this)
            {
                _sending = null;
            }

            ClearDialogs();
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
            _characterName = characterName;
            _sending = this;

            new Thread(() => Listen(listener, Encoding.ASCII.GetBytes(Convert.ToHexString(token))))
            {
                IsBackground = true,
                Name = "AgentBridge"
            }.Start();

            Log.Info($"Agent bridge listening on 127.0.0.1:{port}");
        }

        private void WriteInfoFile(string characterName, uint player, int port, string token)
        {
            string name = SafeFileName(characterName);
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

            AddEvent("message", ("text", e.Text), ("type", e.Type.ToString()), ("serial", serial != 0 ? Hex(serial) : null), ("from", e.Name));

            if (_guardOn)
            {
                CheckTalk(e);
            }

            if (serial == 0)
            {
                string text = e.Text.ToLowerInvariant();

                if (text.Contains("world save has been initiated") || text.Contains("world is saving"))
                {
                    _saving = true;
                    _saveStarted = now;
                }
                else if (text.Contains("world save complete"))
                {
                    _saving = false;
                }
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
                    CheckNoAlarm();

                    return Open(GetSerial(query));

                case "/name":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    // (no alarm check: a single click only asks for a name, allowed while getting away to check a rune)

                    return Name(GetSerials(query));

                case "/close":
                    RequireMethod(method, "POST");
                    uint closeSerial = GetSerial(query);

                    return OnGame(() => Json(w => WriteDone(w, CloseContainer(closeSerial))));

                case "/cancel":
                    RequireMethod(method, "POST");

                    return OnGame(() => Json(w => WriteDone(w, CancelTarget())));

                case "/actions":
                    RequireMethod(method, "GET");

                    return Json
                    (
                        w =>
                        {
                            w.WriteStartArray();

                            foreach ((DateTime time, string what, uint serial) in _actions)
                            {
                                w.WriteStartObject();
                                w.WriteString("time", time.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture));
                                w.WriteString("what", what);
                                w.WriteString("serial", Hex(serial));
                                w.WriteEndObject();
                            }

                            w.WriteEndArray();
                        }
                    );

                case "/resume":
                    RequireMethod(method, "POST");
                    bool wasHalted = _halted != null || _takenOver != null;
                    _halted = null;
                    _takenOver = null;
                    _userActed = null;
                    _burstCount = 0;

                    return Json(w => WriteDone(w, wasHalted));

                case "/rules":
                    RequireMethod(method, "GET");
                    Rules current = RequireRules();

                    return Json(w => current.Write(w));

                case "/walk":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    if (_alarm != null)
                    {
                        _evading = true;
                    }

                    return Walk(query);

                case "/travel":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return Travel(query.TryGetValue("path", out string pathText) ? pathText : "");

                case "/move":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    if (GetInt(query, "ground", 0) == 1)
                    {
                        return DropAtFeet(GetSerial(query), GetInt(query, "amount", 0));
                    }

                    return Move(GetSerial(query), GetSerial(query, "to"), GetInt(query, "x", 0xFFFF), GetInt(query, "y", 0xFFFF), GetInt(query, "amount", 0));

                case "/equip":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return Equip(GetSerial(query));

                case "/use":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    // a spot on the map (a rock face to mine, a forge to smelt at) instead of an item
                    if (query.ContainsKey("x"))
                    {
                        return UseOnTile
                        (
                            GetSerial(query),
                            GetRequiredInt(query, "x"),
                            GetRequiredInt(query, "y"),
                            GetRequiredInt(query, "z"),
                            GetInt(query, "graphic", 0),
                            Math.Clamp(GetInt(query, "reach", REACH), 1, TARGET_REACH)
                        );
                    }

                    // no target: a tool that answers with a menu, a gump or a cursor (a smith's hammer)
                    if (!query.ContainsKey("target"))
                    {
                        return UseTool(GetSerial(query), GetInt(query, "wait", 1) != 0);
                    }

                    return Use(GetSerial(query), GetSerial(query, "target"));

                case "/give":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return Give(GetSerial(query), GetSerial(query, "to"), GetInt(query, "amount", 0));

                case "/trade":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    if (GetInt(query, "cancel", 0) == 0)
                    {
                        CheckNoAlarm();
                    }

                    return Trade(GetInt(query, "accept", -1), GetInt(query, "cancel", 0) != 0);

                case "/cast":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    if (_alarm != null)
                    {
                        _evading = true;
                    }

                    return Cast(GetRequiredInt(query, "spell"), GetSerial(query, "target"), GetInt(query, "cursor", 1) != 0, GetInt(query, "wait", 1) != 0);

                case "/say":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return Say(query.TryGetValue("text", out string text) ? text : "");

                case "/skill":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return UseSkill(GetRequiredInt(query, "id"), query.ContainsKey("target") ? GetSerial(query, "target") : 0, GetInt(query, "cursor", 0) != 0);

                case "/dismount":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Dismount();

                case "/mount":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Mount(GetSerial(query));

                case "/logout":
                    RequireMethod(method, "POST");
                    _logoutRequest = "asked to log out";

                    return Json(w => WriteDone(w, true));

                case "/guard":
                    RequireMethod(method, "POST");
                    bool on = GetInt(query, "on", 1) != 0;
                    Rules guardRules = on ? RequireRules() : null;

                    if (on && guardRules.Guard == null)
                    {
                        throw new BridgeException(403, "the rules file has no guard section for this character");
                    }

                    return OnGame(() => Json(w => WriteGuard(w, SetGuard(on))));

                case "/animations":
                    RequireMethod(method, "GET");

                    return OnGame(() => Json(WriteAnimations));

                case "/tiles":
                    RequireMethod(method, "GET");
                    int tileRange = Math.Clamp(GetInt(query, "range", 3), 0, MAX_TILE_RANGE);

                    return OnGame(() => Json(w => WriteTiles(w, tileRange)));
            }

            byte[] dialogAnswer = HandleDialogs(method, path, query);

            if (dialogAnswer != null)
            {
                return dialogAnswer;
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
                        LogAction("open (double-click)", serial);
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
                        LogAction("name (single-click)", serial);
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
            bool run = GetInt(query, "run", 0) != 0;

            // wait=0 (fights only): start the walk and come back at once, without waiting a turn: steps aren't actions,
            // and getting away from a creature can't wait. The path isn't watched for leaving the areas then.
            bool wait = GetInt(query, "wait", 1) != 0;

            if (!wait && !rules.Fight)
            {
                throw new BridgeException(403, "only a character the rules let fight walks without waiting");
            }

            // a walk waits its turn like any other action, so nothing happens the instant he arrives somewhere
            if (wait)
            {
                WaitForActionSlot();
            }

            bool toItem = query.ContainsKey("to");
            uint target = toItem ? GetSerial(query, "to") : 0;
            int x = toItem ? 0 : GetRequiredInt(query, "x");
            int y = toItem ? 0 : GetRequiredInt(query, "y");
            int distance = Math.Clamp(GetInt(query, "distance", toItem ? 1 : 0), 0, 10);

            AreaWatch area = null;

            (int destX, int destY, bool already) = OnGame
            (
                () =>
                {
                    CheckNobodyElse(rules);
                    PlayerMobile p = _world.Player;
                    int dx = x, dy = y;
                    area = new AreaWatch(m => rules.Contains(_world.MapIndex, m.X, m.Y, m.Z), p);

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

                    if (!p.Pathfinder.WalkTo(dx, dy, p.Z, distance, run))
                    {
                        throw new BridgeException(409, "no path to there");
                    }

                    return (dx, dy, false);
                }
            );

            bool leftArea = false;

            if (!wait)
            {
                return OnGame
                (
                    () => Json
                    (
                        w =>
                        {
                            PlayerMobile p = _world.Player;

                            w.WriteStartObject();
                            w.WriteBoolean("arrived", already);
                            w.WriteBoolean("walking", !already && p.Pathfinder.AutoWalking);
                            w.WriteNumber("x", p.X);
                            w.WriteNumber("y", p.Y);
                            w.WriteNumber("z", p.Z);
                            w.WriteEndObject();
                        }
                    )
                );
            }

            if (already)
            {
                PaceFromNow();
            }
            else
            {
                Thread.Sleep(POLL_INTERVAL * 2);

                // the path finder may step round an obstacle outside the area: stop the moment that happens
                WaitFor
                (
                    () =>
                    {
                        PlayerMobile p = _world.Player;
                        leftArea = area.Left(p);

                        return leftArea || !p.Pathfinder.AutoWalking;
                    },
                    WALK_TIMEOUT
                );

                if (leftArea)
                {
                    OnGame
                    (
                        () =>
                        {
                            _world.Player.Pathfinder.StopAutoWalk();

                            return true;
                        }
                    );
                }

                // and the next action waits a full gap from arriving
                PaceFromNow();
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

                        if (leftArea)
                        {
                            w.WriteBoolean("leftArea", true);
                        }
                        w.WriteNumber("x", p.X);
                        w.WriteNumber("y", p.Y);
                        w.WriteNumber("z", p.Z);
                        w.WriteNumber("tilesLeft", left);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // rides a path planned in advance ("x,y;x,y;..." waypoints, each a stretch the client's path finder can see)
        // in one go: the next stretch starts a few tiles before the current one ends, so he keeps moving. Stops when
        // an alarm goes off, a step leaves the agent's areas, or he makes no progress. The whole ride is one action.
        private byte[] Travel(string pathText)
        {
            Rules rules = RequireRules();
            var points = new List<(int X, int Y)>();

            foreach (string pair in pathText.Split(';', StringSplitOptions.RemoveEmptyEntries))
            {
                string[] xy = pair.Split(',');

                if (xy.Length != 2 || !int.TryParse(xy[0], out int px) || !int.TryParse(xy[1], out int py))
                {
                    throw new BridgeException(400, $"not a waypoint: {pair}");
                }

                points.Add((px, py));
            }

            if (points.Count == 0 || points.Count > 200)
            {
                throw new BridgeException(400, "give 1 to 200 waypoints as path=x,y;x,y;...");
            }

            AreaWatch area = OnGame
            (
                () =>
                {
                    foreach ((int px, int py) in points)
                    {
                        if (!rules.Contains(_world.MapIndex, px, py, _world.Player.Z))
                        {
                            throw new BridgeException(403, $"waypoint {px},{py} is outside the agent's area");
                        }
                    }

                    return new AreaWatch(m => rules.Contains(_world.MapIndex, m.X, m.Y, m.Z), _world.Player);
                }
            );

            WaitForActionSlot("travel");

            int next = 0;     // the waypoint being ridden to
            int tryIndex = 0; // the next waypoint to hand over to
            bool leftArea = false;
            string stopped = null;
            DateTime end = DateTime.UtcNow.AddMilliseconds(TRAVEL_TIMEOUT);
            DateTime lastProgress = DateTime.UtcNow;
            int best = int.MaxValue;
            bool walking = false;

            while (stopped == null)
            {
                if (_alarm != null)
                {
                    stopped = "alarm";

                    break;
                }

                (int x, int y, bool auto, bool outside) = OnGame
                (
                    () =>
                    {
                        PlayerMobile p = _world.Player;
                        bool isOutside = area.Left(p);

                        if (isOutside)
                        {
                            p.Pathfinder.StopAutoWalk();
                        }
                        else if (tryIndex < points.Count)
                        {
                            int left = Math.Max(Math.Abs(p.X - points[next].X), Math.Abs(p.Y - points[next].Y));

                            // close to this stretch's end (or it ended): hand over to the next waypoint. One search
                            // per check (a failed one can take a while, and this is the game's own update); if it
                            // finds no way, the next check tries the waypoint after it.
                            if (!walking || left <= TRAVEL_HANDOVER || !p.Pathfinder.AutoWalking)
                            {
                                if (p.Pathfinder.WalkTo(points[tryIndex].X, points[tryIndex].Y, p.Z, tryIndex == points.Count - 1 ? 1 : 2))
                                {
                                    next = tryIndex;
                                    walking = true;
                                }

                                tryIndex++;
                            }
                        }

                        return (p.X, p.Y, p.Pathfinder.AutoWalking, isOutside);
                    }
                );

                if (outside)
                {
                    leftArea = true;
                    stopped = "left the area";

                    break;
                }

                (int lastX, int lastY) = points[points.Count - 1];
                int toEnd = Math.Max(Math.Abs(x - lastX), Math.Abs(y - lastY));

                if (toEnd <= 1 && !auto)
                {
                    break;
                }

                if (toEnd < best)
                {
                    best = toEnd;
                    lastProgress = DateTime.UtcNow;
                }
                else if ((DateTime.UtcNow - lastProgress).TotalMilliseconds > TRAVEL_STUCK)
                {
                    stopped = "no progress";

                    break;
                }

                if (DateTime.UtcNow > end)
                {
                    stopped = "took too long";

                    break;
                }

                Thread.Sleep(POLL_INTERVAL * 2);
            }

            if (stopped != null)
            {
                OnGame
                (
                    () =>
                    {
                        _world.Player.Pathfinder.StopAutoWalk();

                        return true;
                    }
                );
            }

            PaceFromNow();

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        PlayerMobile p = _world.Player;
                        (int lastX, int lastY) = points[points.Count - 1];

                        w.WriteStartObject();
                        w.WriteBoolean("arrived", Math.Max(Math.Abs(p.X - lastX), Math.Abs(p.Y - lastY)) <= 1);
                        w.WriteNumber("x", p.X);
                        w.WriteNumber("y", p.Y);
                        w.WriteNumber("z", p.Z);
                        w.WriteNumber("reached", next);

                        if (stopped != null)
                        {
                            w.WriteString("stopped", stopped);
                        }

                        if (leftArea)
                        {
                            w.WriteBoolean("leftArea", true);
                        }

                        w.WriteEndObject();
                    }
                )
            );
        }

        // "left the area", for a walk or a ride: a step took him from inside the agent's area to outside it. One that
        // starts outside (the path finder stepped Icepick a tile over the edge, 2026-11-05 09:38, and every walk after
        // stopped at once, back in too) may carry on, for a few steps outside, until he's back in.
        private sealed class AreaWatch
        {
            private readonly Func<PlayerMobile, bool> _inside;
            private bool _beenInside;
            private int _stepsOutside;
            private int _x, _y;

            public AreaWatch(Func<PlayerMobile, bool> inside, PlayerMobile p)
            {
                _inside = inside;
                _beenInside = inside(p);
                _x = p.X;
                _y = p.Y;
            }

            public bool Left(PlayerMobile p)
            {
                if (_inside(p))
                {
                    _beenInside = true;

                    return false;
                }

                if (_beenInside)
                {
                    return true;
                }

                if (p.X != _x || p.Y != _y)
                {
                    _stepsOutside++;
                    _x = p.X;
                    _y = p.Y;
                }

                return _stepsOutside > STEPS_BACK_IN;
            }
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
                    LogAction("drop", serial);
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

        // puts a carried item (or part of a stack) down on the character's own tile; only kinds the rules list under
        // "dropOnGround" (ore: a dig that overloads the miner leaves him too tired to ride, the user, 2026-11-02)
        private byte[] DropAtFeet(uint serial, int amount)
        {
            Rules rules = RequireRules();
            int x = 0, y = 0, z = 0;

            long before = Lift
            (
                serial,
                rules,
                item =>
                {
                    if (!rules.DropOnGround.Contains(item.Graphic))
                    {
                        throw new BridgeException(403, "the rules don't allow putting that on the ground (dropOnGround)");
                    }

                    if (!IsCarried(item))
                    {
                        throw new BridgeException(403, "only something carried can be put down");
                    }

                    PlayerMobile p = _world.Player;

                    if (!rules.Contains(_world.MapIndex, p.X, p.Y, p.Z))
                    {
                        throw new BridgeException(403, "the character is outside the agent's area");
                    }

                    (x, y, z) = (p.X, p.Y, p.Z);
                },
                amount
            );

            OnGame
            (
                () =>
                {
                    LogAction("drop on the ground", serial);
                    GameActions.DropItem(serial, x, y, z, 0xFFFF_FFFF);

                    return true;
                }
            );

            PaceFromNow();

            bool answered = WaitFor(() => _world.Items.Get(serial)?.OnGround ?? false, MOVE_TIMEOUT);
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

                Halt($"no answer after putting {Hex(serial)} down");
            }

            return OnGame
            (
                () =>
                {
                    Item item = _world.Items.Get(serial);
                    bool down = item != null && item.OnGround;

                    ReleaseHeldItem();

                    return Json
                    (
                        w =>
                        {
                            w.WriteStartObject();
                            w.WriteBoolean("moved", down);
                            w.WriteNumber("weight", _world.Player.Weight);

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
                    LogAction("equip", serial);
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
            CheckNoPendingAim();
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
                        CheckUsable(item, rules);

                        if (SerialHelper.IsMobile(target))
                        {
                            CheckPatient(target, rules);
                        }
                        else
                        {
                            Item aim = _world.Items.Get(target) ?? throw new BridgeException(404, "no such target nearby");
                            CheckInReach(CheckReachable(aim, rules, "target"), TARGET_REACH);
                        }

                        if (_world.TargetManager.IsTargeting)
                        {
                            _world.TargetManager.CancelTarget();
                        }

                        LogAction("use (double-click)", serial);
                        GameActions.DoubleClick(_world, serial);

                        return _lastMessageId;
                    }
                );

                WaitFor(() => _world.TargetManager.IsTargeting || HasSystemMessageAfter(before), TARGET_TIMEOUT);
                targeting = OnGame(() => _world.TargetManager.IsTargeting);

                // bandages ask first ("Who will you use the bandages on?"), with the cursor right behind the words
                if (!targeting && !OnGame(() => SawMessage(before, MUST_WAIT)))
                {
                    WaitFor(() => _world.TargetManager.IsTargeting, SETTLE_TIME);
                    targeting = OnGame(() => _world.TargetManager.IsTargeting);
                }

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
                Aim(rules);

                long aimed = OnGame
                (
                    () =>
                    {
                        LogAction("target", target);
                        _world.TargetManager.Target(target);

                        return _lastMessageId;
                    }
                );

                // a tool like scissors answers by using the target up (it disappears) rather than with a message, and
                // ore combined into another pile disappears itself without a word
                // (a patient answers with a message: "You begin applying the bandages.")
                bool onItem = !SerialHelper.IsMobile(target);

                if (WaitFor(() => HasMessageFrom(target, aimed) || HasSystemMessageAfter(aimed) || onItem && _world.Items.Get(target) == null || _world.Items.Get(serial) == null, USE_RESULT_TIMEOUT))
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

                        Mobile patient = SerialHelper.IsMobile(target) ? _world.Mobiles.Get(target) : null;

                        if (patient != null)
                        {
                            w.WriteStartObject("patient");
                            w.WriteString("serial", Hex(patient.Serial));
                            w.WriteString("name", patient.Name ?? "");
                            w.WriteBoolean("dead", patient.IsDead);
                            w.WriteNumber("hits", patient.Hits);
                            w.WriteNumber("hitsMax", patient.HitsMax);
                            w.WriteNumber("distance", patient.Distance);
                            w.WriteEndObject();
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

                        LogAction("pick up", serial);
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

        // only an item in the hands, or a tool the rules allow from the backpack, is ever double-clicked
        private void CheckUsable(Item item, Rules rules)
        {
            bool inHands = item.Container == _world.Player.Serial && (item.Layer == Layer.OneHanded || item.Layer == Layer.TwoHanded);
            bool allowedTool = rules.UseFromBackpack.Contains(item.Graphic) && IsCarried(item);

            // a key ring the rules name, locked down by the front door: used where it is, from within reach
            if (rules.Keys.Contains(item.Serial) && item.OnGround)
            {
                CheckInReach(item, REACH);

                return;
            }

            // a kind the rules let it use where it lies (a pile of bandages on the floor), inside the area, within reach
            if (item.OnGround && rules.UseOnGround.Contains(item.Graphic))
            {
                CheckInReach(CheckReachable(item, rules, "use"), REACH);

                return;
            }

            if (!inHands && !allowedTool)
            {
                throw new BridgeException(403, "only an item in the character's hands, a tool the rules allow from the backpack, or a kind they allow where it lies, can be used");
            }
        }

        // uses a tool on a spot on the map instead of an item: a pickaxe on a rock face, ore on a forge.
        // graphic 0 aims at the ground itself (mountain and cave floors are ground); anything else is a static there
        private byte[] UseOnTile(uint serial, int x, int y, int z, int graphic, int reach)
        {
            Rules rules = RequireRules();
            long before = 0;
            bool targeting = false;
            bool repeat = false;

            for (int attempt = 0; attempt < 2 && !targeting; attempt++)
            {
                repeat = WaitForActionSlot($"use {Hex(serial)} at {x},{y},{z}");

                before = OnGame
                (
                    () =>
                    {
                        CheckNobodyElse(rules);
                        Item item = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such item nearby");
                        CheckUsable(item, rules);

                        if (!rules.ContainsSpot(_world.MapIndex, x, y))
                        {
                            throw new BridgeException(403, "that spot is outside the agent's area");
                        }

                        PlayerMobile p = _world.Player;
                        int distance = Math.Max(Math.Abs(p.X - x), Math.Abs(p.Y - y));

                        if (distance > reach)
                        {
                            throw new BridgeException(409, $"too far away ({distance} tiles, reach is {reach}); walk closer first");
                        }

                        if (_world.TargetManager.IsTargeting)
                        {
                            _world.TargetManager.CancelTarget();
                        }

                        LogAction("use (double-click)", serial);
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

            bool sent = false;

            if (targeting)
            {
                Aim(rules, repeat);

                (long aimed, bool stillTargeting) = OnGame
                (
                    () =>
                    {
                        LogAction($"target {x},{y},{z} {Hex((ushort)graphic)}", 0);
                        long id = _lastMessageId;
                        _world.TargetManager.Target((ushort)graphic, (ushort)x, (ushort)y, (short)z);

                        // the client refuses a ground spot when the cursor wants an object, and sends nothing
                        return (id, _world.TargetManager.IsTargeting);
                    }
                );

                sent = !stillTargeting;

                if (sent)
                {
                    // mining and smelting answer after the swing, with a message from the server (not, say, the
                    // name of a bird that just flew into view)
                    if (WaitFor(() => HasSystemMessageAfter(aimed), LAND_RESULT_TIMEOUT))
                    {
                        Thread.Sleep(SETTLE_TIME);
                    }
                    else
                    {
                        OnGame(CancelTarget);
                        Halt($"no answer after targeting {x},{y},{z}");
                    }
                }
            }

            OnGame(CancelTarget);

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        w.WriteStartObject();
                        w.WriteBoolean("targeted", sent);

                        if (targeting && !sent)
                        {
                            w.WriteString("refused", "the cursor wants an object, not a spot on the ground");
                        }

                        WriteMessagesSince(w, before, 0);
                        w.WriteNumber("weight", _world.Player.Weight);
                        w.WriteNumber("weightMax", _world.Player.WeightMax);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // hands a carried item to one of the user's own characters: dropping it on them opens the trade window
        private byte[] Give(uint serial, uint to, int amount)
        {
            Rules rules = RequireRules();

            long before = Lift
            (
                serial,
                rules,
                item =>
                {
                    if (!IsCarried(item))
                    {
                        throw new BridgeException(403, "only things the character carries can be given");
                    }

                    Mobile m = _world.Mobiles.Get(to) ?? throw new BridgeException(404, "no such character nearby");

                    if (!IsPartner(m, rules))
                    {
                        throw new BridgeException(403, "things can only be given to a partner named in the rules");
                    }

                    if (m.Distance > REACH)
                    {
                        throw new BridgeException(409, $"too far away ({m.Distance} tiles, reach is {REACH}); walk closer first");
                    }
                },
                amount
            );

            OnGame
            (
                () =>
                {
                    LogAction("drop on partner", to);
                    GameActions.DropItem(serial, 0xFFFF, 0xFFFF, 0, to);

                    return true;
                }
            );

            PaceFromNow();

            bool answered = WaitFor(() => UIManager.GetTradingGump(to) != null || HasSystemMessageAfter(before), TRADE_TIMEOUT);
            Thread.Sleep(SETTLE_TIME);

            if (!answered)
            {
                OnGame
                (
                    () =>
                    {
                        ReleaseHeldItem();

                        return true;
                    }
                );

                Halt($"no answer after giving {Hex(serial)}");
            }

            return OnGame
            (
                () =>
                {
                    ReleaseHeldItem();

                    return Json
                    (
                        w =>
                        {
                            w.WriteStartObject();
                            WriteTrade(w);
                            WriteMessagesSince(w, before, 0);
                            w.WriteEndObject();
                        }
                    );
                }
            );
        }

        // ticks or unticks this side's accept box in the open trade window, or cancels the trade.
        // When both sides accept, the server swaps the items and closes the window.
        private byte[] Trade(int accept, bool cancel)
        {
            Rules rules = RequireRules();

            if (!cancel && accept < 0)
            {
                throw new BridgeException(400, "give accept=1, accept=0 or cancel=1");
            }

            WaitForActionSlot();

            uint partner = OnGame
            (
                () =>
                {
                    TradingGump gump = FindTrade() ?? throw new BridgeException(404, "no trade window is open");

                    if (cancel)
                    {
                        LogAction("cancel trade", gump.LocalSerial);
                        GameActions.CancelTrade(gump.ID1);

                        return gump.LocalSerial;
                    }

                    Mobile m = _world.Mobiles.Get(gump.LocalSerial);

                    if (m == null || !IsPartner(m, rules))
                    {
                        throw new BridgeException(403, "trades are only accepted with a partner named in the rules");
                    }

                    LogAction(accept != 0 ? "accept trade" : "unaccept trade", gump.LocalSerial);
                    GameActions.AcceptTrade(gump.ID1, accept != 0);

                    return gump.LocalSerial;
                }
            );

            // the server answers with both boxes' state, or closes the window when the trade is done
            WaitFor
            (
                () =>
                {
                    TradingGump gump = UIManager.GetTradingGump(partner);

                    return gump == null || !cancel && gump.ImAccepting == (accept != 0);
                },
                TRADE_TIMEOUT
            );

            Thread.Sleep(SETTLE_TIME);

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        w.WriteStartObject();
                        WriteTrade(w);
                        w.WriteEndObject();
                    }
                )
            );
        }

        private static TradingGump FindTrade()
        {
            for (LinkedListNode<Gump> node = UIManager.Gumps.First; node != null; node = node.Next)
            {
                if (node.Value is TradingGump trade && !trade.IsDisposed)
                {
                    return trade;
                }
            }

            return null;
        }

        // casts a spell the rules allow (Recall is 32) on something the character carries (a rune)
        private byte[] Cast(int spell, uint target, bool cursor = true, bool wait = true)
        {
            Rules rules = RequireRules();

            if (!rules.Spells.Contains(spell))
            {
                throw new BridgeException(403, "the rules don't allow that spell");
            }

            if (SerialHelper.IsMobile(target))
            {
                return CastAt(spell, target, rules, cursor, wait);
            }

            WaitForActionSlot();

            (long before, int x0, int y0) = OnGame
            (
                () =>
                {
                    CheckNobodyElse(rules);
                    Item aim = _world.Items.Get(target) ?? throw new BridgeException(404, "no such target nearby");

                    if (!IsCarried(aim))
                    {
                        throw new BridgeException(403, "spells are only cast on things the character carries");
                    }

                    if (_world.TargetManager.IsTargeting)
                    {
                        _world.TargetManager.CancelTarget();
                    }

                    LogAction($"cast spell {spell}", target);
                    GameActions.CastSpell(spell);

                    return (_lastMessageId, (int)_world.Player.X, (int)_world.Player.Y);
                }
            );

            // a fizzle, too little mana or missing reagents come back as messages instead of a cursor
            WaitFor(() => _world.TargetManager.IsTargeting || HasSystemMessageAfter(before), CAST_TIMEOUT);
            bool targeting = OnGame(() => _world.TargetManager.IsTargeting);

            if (!targeting && !OnGame(() => HasMessageAfter(before)))
            {
                Halt($"no answer when casting spell {spell}");
            }

            bool moved = false;

            if (targeting)
            {
                Aim(rules);

                long aimed = OnGame
                (
                    () =>
                    {
                        LogAction("target", target);
                        long id = _lastMessageId;
                        _world.TargetManager.Target(target);

                        return id;
                    }
                );

                // "The spell fizzles." and "You open a magical gate" come from the caster or the server
                if (!WaitFor(() => _world.Player.X != x0 || _world.Player.Y != y0 || HasSystemMessageAfter(aimed) || HasMessageFrom(_world.Player.Serial, aimed), RECALL_TIMEOUT))
                {
                    OnGame(CancelTarget);
                    Halt($"no answer after targeting {Hex(target)} with spell {spell}");
                }

                Thread.Sleep(SETTLE_TIME);
                moved = OnGame(() => _world.Player.X != x0 || _world.Player.Y != y0);
            }

            OnGame(CancelTarget);
            PaceFromNow();

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        PlayerMobile p = _world.Player;

                        w.WriteStartObject();
                        w.WriteBoolean("targeted", targeting);
                        w.WriteBoolean("moved", moved);
                        w.WriteNumber("x", p.X);
                        w.WriteNumber("y", p.Y);
                        w.WriteNumber("z", p.Z);
                        w.WriteNumber("mana", p.Mana);
                        WriteMessagesSince(w, before, 0);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // a spell at a creature (a bolt) or at the character himself (a heal), in a fight: casts, aims the moment the
        // cursor shows and comes back; the spell lands (or fizzles) a moment later. Never halts: whatever the server
        // says is in the answer's messages ("More reagents are needed for this spell.", "Target is not in line of sight.")
        // cursor false: a spell that brings no target cursor (Magic Reflection on himself, target = the character):
        // answered as soon as he has said the words or the server has said something, instead of waiting out
        // CAST_TIMEOUT for a cursor that never comes (the spell takes about half a second; the user, 2026-11-06).
        // wait false: answered as soon as the spell is sent; its cursor is aimed from Update when it comes (AimPending)
        // and the outcome is left to the messages, so the agent goes on moving and looking meanwhile
        private byte[] CastAt(int spell, uint target, Rules rules, bool cursor = true, bool wait = true)
        {
            OnGame(() => CheckFightTarget(target, rules));
            WaitForActionSlot();

            long before = OnGame
            (
                () =>
                {
                    CheckFightTarget(target, rules);

                    if (_world.TargetManager.IsTargeting)
                    {
                        _world.TargetManager.CancelTarget();
                    }

                    LogAction($"cast spell {spell}", target);
                    long id = _lastMessageId;
                    _aimTarget = 0;
                    GameActions.CastSpell(spell);

                    if (!wait && cursor)
                    {
                        _aimTarget = target;
                        _aimUntil = DateTime.UtcNow.AddMilliseconds(CAST_TIMEOUT);
                    }

                    return id;
                }
            );

            if (!wait)
            {
                PaceFromNow();

                return OnGame
                (
                    () => Json
                    (
                        w =>
                        {
                            w.WriteStartObject();
                            w.WriteBoolean("cast", true);
                            w.WriteNumber("messageId", before);
                            w.WriteNumber("hits", _world.Player.Hits);
                            w.WriteNumber("mana", _world.Player.Mana);
                            w.WriteEndObject();
                        }
                    )
                );
            }

            if (!cursor)
            {
                WaitFor(() => HasSystemMessageAfter(before) || HasMessageFrom(_world.Player.Serial, before), NO_CURSOR_TIMEOUT);
                Thread.Sleep(SETTLE_TIME);
            }
            else
            {
                WaitFor(() => _world.TargetManager.IsTargeting || HasSystemMessageAfter(before), CAST_TIMEOUT);
            }

            bool aimed = false;

            if (cursor && OnGame(() => _world.TargetManager.IsTargeting))
            {
                Aim(rules);

                aimed = OnGame
                (
                    () =>
                    {
                        Mobile m = _world.Mobiles.Get(target);

                        // died or ran off while the words were said: no aim (the cursor is cancelled below)
                        if (m == null || m.IsDestroyed || m.IsDead && m != _world.Player)
                        {
                            return false;
                        }

                        // the user took over meanwhile: the cursor may be theirs, so leave it to them
                        if (_takenOver != null || _userActed != null)
                        {
                            return false;
                        }

                        LogAction("target", target);
                        _world.TargetManager.Target(target);

                        return true;
                    }
                );

                Thread.Sleep(SETTLE_TIME);
            }

            if (OnGame(() => _takenOver == null && _userActed == null))
            {
                OnGame(CancelTarget);
            }

            PaceFromNow();

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        PlayerMobile p = _world.Player;

                        w.WriteStartObject();
                        w.WriteBoolean("aimed", aimed);
                        w.WriteNumber("hits", p.Hits);
                        w.WriteNumber("mana", p.Mana);
                        WriteMessagesSince(w, before, 0);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // game thread, from Update: a spell cast with wait=0 has brought its cursor: aim it at the creature (or him).
        // Given up when the time is out or the user takes over (the cursor may be theirs); a creature that died or
        // went meanwhile gets the cursor cancelled
        private void AimPending()
        {
            if (_takenOver != null || _userActed != null || DateTime.UtcNow > _aimUntil)
            {
                _aimTarget = 0;

                return;
            }

            if (!_world.TargetManager.IsTargeting)
            {
                return;
            }

            uint target = _aimTarget;
            _aimTarget = 0;
            Mobile m = _world.Mobiles.Get(target);

            if (m == null || m.IsDestroyed || m.IsDead && m != _world.Player)
            {
                LogAction("cancel target (gone)", target);
                _world.TargetManager.CancelTarget();

                return;
            }

            LogAction("target", target);
            _world.TargetManager.Target(target);
        }

        // game thread: one of the user's own characters the rules name as a patient (Isabel's ghost, for bandages),
        // alive or dead, within reach: a bandage reaches 1 tile on this server's era (2 from AOS on), and the server
        // says "You are too far away" itself, but nothing further than REACH is ever aimed at
        private Mobile CheckPatient(uint serial, Rules rules)
        {
            Mobile m = _world.Mobiles.Get(serial) ?? throw new BridgeException(404, "no such character nearby");

            if (!rules.Patients.Contains(Hex(m.Serial)) && !rules.Patients.Contains(m.Name ?? ""))
            {
                throw new BridgeException(403, "the rules don't name that character as a patient");
            }

            if (m.IsDestroyed)
            {
                throw new BridgeException(404, "that character has gone");
            }

            if (m.Distance > REACH)
            {
                throw new BridgeException(409, $"too far away ({m.Distance} tiles, reach is {REACH}); walk closer first");
            }

            return m;
        }

        // game thread: a creature the rules let the character aim skills and spells at: one anybody may attack (gray,
        // criminal, enemy, murderer), not a person or a pet, within FIGHT_RANGE; or the character himself (a heal).
        // Never anything blue or green, so a fight can't make him a criminal or touch another player.
        private Mobile CheckFightTarget(uint serial, Rules rules)
        {
            if (!rules.Fight)
            {
                throw new BridgeException(403, "the rules don't let this character aim at creatures");
            }

            Mobile m = _world.Mobiles.Get(serial) ?? throw new BridgeException(404, "no such creature nearby");

            if (m == _world.Player)
            {
                return m;
            }

            if (m.IsDestroyed || m.IsDead)
            {
                throw new BridgeException(409, "that creature is dead");
            }

            if (m.IsHuman || m.IsRenamable)
            {
                throw new BridgeException(403, "never a person or a pet");
            }

            if (m.NotorietyFlag != NotorietyFlag.Gray && m.NotorietyFlag != NotorietyFlag.Criminal && m.NotorietyFlag != NotorietyFlag.Enemy && m.NotorietyFlag != NotorietyFlag.Murderer)
            {
                throw new BridgeException(403, $"only creatures anybody may attack (this one is {m.NotorietyFlag})");
            }

            if (m.Distance > FIGHT_RANGE)
            {
                throw new BridgeException(409, $"too far away ({m.Distance} tiles, the most is {FIGHT_RANGE})");
            }

            return m;
        }

        // double-clicks one of the doors in the rules (it opens or closes) and waits until it has moved
        private byte[] UseDoor(uint serial, Rules rules)
        {
            WaitForActionSlot();

            (long before, ushort graphic, int x, int y) = OnGame
            (
                () =>
                {
                    Item door = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such door nearby");
                    CheckInReach(door, REACH);

                    if (_world.TargetManager.IsTargeting)
                    {
                        _world.TargetManager.CancelTarget();
                    }

                    LogAction("use door (double-click)", serial);
                    long id = _lastMessageId;
                    GameActions.DoubleClick(_world, serial);

                    return (id, door.Graphic, (int)door.X, (int)door.Y);
                }
            );

            // "This door is locked." and the like come as messages; an opened or closed door changes its art and place
            WaitFor
            (
                () =>
                {
                    Item door = _world.Items.Get(serial);

                    return door == null || door.Graphic != graphic || door.X != x || door.Y != y || HasSystemMessageAfter(before);
                },
                TARGET_TIMEOUT
            );

            Thread.Sleep(SETTLE_TIME);
            PaceFromNow();

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        Item door = _world.Items.Get(serial);

                        w.WriteStartObject();
                        w.WriteBoolean("moved", door == null || door.Graphic != graphic || door.X != x || door.Y != y);

                        if (door != null)
                        {
                            w.WriteString("graphic", Hex(door.Graphic));
                            w.WriteNumber("x", door.X);
                            w.WriteNumber("y", door.Y);
                        }

                        WriteMessagesSince(w, before, 0);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // says one of the few words the rules allow ("bank"); never anything else, so it can't talk to players
        private byte[] Say(string text)
        {
            Rules rules = RequireRules();
            CheckNoPendingAim();
            text = text.Trim();

            if (text.Length == 0 || !rules.Say.Contains(text))
            {
                throw new BridgeException(403, "the rules don't allow saying that");
            }

            WaitForActionSlot();

            long before = OnGame
            (
                () =>
                {
                    CheckNobodyElse(rules);
                    LogAction($"say \"{text}\"", 0);
                    long id = _lastMessageId;
                    GameActions.Say(text);

                    return id;
                }
            );

            Thread.Sleep(1000); // the banker opens the bank box, which needs no other answer

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        w.WriteStartObject();
                        Item bank = _world.Player.FindItemByLayer(Layer.Bank);

                        if (bank != null)
                        {
                            w.WritePropertyName("bank");
                            WriteItem(w, bank);
                        }

                        WriteMessagesSince(w, before, 0);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // on the game thread: remember an animation, and mark anyone doing an NPC's idle fidget as an NPC
        private void NoteAnimation(uint serial, ushort action)
        {
            Mobile m = _world.Mobiles.Get(serial);

            if (m == null || m == _world.Player)
            {
                return;
            }

            _animations.Enqueue((DateTime.Now, serial, m.Name, action, m.X, m.Y));

            while (_animations.Count > ANIMATION_LOG)
            {
                _animations.Dequeue();
            }

            Rules rules = _rules;
            GuardRules g = rules?.Guard;

            if (g != null && g.Fidgets.Contains(action) && !IsPartner(m, rules) && LoadLearnedNpcs().Add(serial))
            {
                Log.Info($"Agent bridge: {Describe(m, serial)} fidgets (animation {action}): an NPC");
                SaveLearnedNpcs();
            }
        }

        private static string LearnedNpcsPath() => Path.Combine(CUOEnviroment.ExecutablePath, "Agent", "npcs-learned.json");

        private HashSet<uint> LoadLearnedNpcs()
        {
            if (!_npcLoaded)
            {
                _npcLoaded = true;

                try
                {
                    if (File.Exists(LearnedNpcsPath()))
                    {
                        using JsonDocument doc = JsonDocument.Parse(File.ReadAllBytes(LearnedNpcsPath()));

                        foreach (JsonElement e in doc.RootElement.EnumerateArray())
                        {
                            if (TryParseSerial(e.GetProperty("serial").GetString(), out uint serial))
                            {
                                _npcLearned.Add(serial);
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    Log.Warn($"Agent bridge: could not read the learned NPCs: {ex.Message}");
                }
            }

            return _npcLearned;
        }

        private void SaveLearnedNpcs()
        {
            try
            {
                File.WriteAllBytes
                (
                    LearnedNpcsPath(),
                    Json
                    (
                        w =>
                        {
                            w.WriteStartArray();

                            foreach (uint serial in _npcLearned)
                            {
                                w.WriteStartObject();
                                w.WriteString("serial", Hex(serial));
                                w.WriteString("name", _world.Mobiles.Get(serial)?.Name);
                                w.WriteEndObject();
                            }

                            w.WriteEndArray();
                        }
                    )
                );
            }
            catch (Exception ex)
            {
                Log.Warn($"Agent bridge: could not save the learned NPCs: {ex.Message}");
            }
        }

        private void WriteAnimations(Utf8JsonWriter w)
        {
            w.WriteStartObject();
            w.WriteStartArray("animations");

            foreach ((DateTime time, uint serial, string name, ushort action, int x, int y) in _animations)
            {
                w.WriteStartObject();
                w.WriteString("time", time.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture));
                w.WriteString("serial", Hex(serial));
                w.WriteString("name", name);
                w.WriteNumber("action", action);
                w.WriteNumber("x", x);
                w.WriteNumber("y", y);
                w.WriteEndObject();
            }

            w.WriteEndArray();
            w.WriteStartArray("npcsLearned");

            foreach (uint serial in LoadLearnedNpcs())
            {
                w.WriteStringValue(Hex(serial));
            }

            w.WriteEndArray();
            w.WriteEndObject();
        }

        // ---- the guard, on the game thread ----

        // (re)starting the guard also clears an alarm: the agent calls it once the person has gone
        private bool SetGuard(bool on)
        {
            _guardOn = on;
            _nearSince.Clear();
            _seenCarried.Clear();
            _lastHits = -1;
            _alarm = null;
            _threat = null;
            _evading = false;
            _lastLogged = null;

            if (on)
            {
                _guardSince = DateTime.UtcNow;
                _nextGuardCheck = DateTime.MinValue;
                _nextAlarmFileCheck = DateTime.MinValue;
                _alarmFileSeen = AlarmFileTime(); // alarms written before now are old news
                Log.Info("Agent bridge guard on");
            }

            return on;
        }

        private void GuardTick()
        {
            DateTime now = DateTime.UtcNow;

            if (now < _nextGuardCheck)
            {
                return;
            }

            _nextGuardCheck = now.AddMilliseconds(GUARD_INTERVAL);

            Rules rules = _rules;
            GuardRules g = rules?.Guard;
            PlayerMobile p = _world.Player;

            if (g == null || p == null)
            {
                return;
            }

            if (_alarm != null)
            {
                // keep track of where the person is, for the agent deciding when they've gone
                Mobile seen = _threat != null && _threat.Serial != 0 ? _world.Mobiles.Get(_threat.Serial) : null;

                if (seen != null && !seen.IsDestroyed)
                {
                    _threat.X = seen.X;
                    _threat.Y = seen.Y;
                    _threat.Seen = now;
                }

                // nobody is getting the character away (the agent's script isn't running): hide where he stands,
                // on his horse first if it's beside him (a riderless horse next to a hidden man gives him away)
                if (!_evading && now >= _nextAutoHide && !p.IsHidden && rules.Skills.Contains(HIDING))
                {
                    Mobile horse = null;

                    if (p.FindItemByLayer(Layer.Mount) == null)
                    {
                        foreach (uint serial in rules.Mounts)
                        {
                            Mobile m = _world.Mobiles.Get(serial);

                            if (m != null && !m.IsDestroyed && m.Distance <= REACH)
                            {
                                horse = m;
                            }
                        }
                    }

                    if (horse != null)
                    {
                        _nextAutoHide = now.AddSeconds(3);
                        Log.Warn("Agent bridge guard: nobody is getting the character away; mounting to hide");
                        GameActions.DoubleClick(_world, horse.Serial);
                    }
                    else
                    {
                        _nextAutoHide = now.AddSeconds(11);
                        Log.Warn("Agent bridge guard: nobody is getting the character away; hiding");
                        GameActions.UseSkill(HIDING);
                    }
                }
            }

            // the partner's guard went off: stop work here too
            if (now >= _nextAlarmFileCheck)
            {
                _nextAlarmFileCheck = now.AddMilliseconds(ALARM_FILE_INTERVAL);
                DateTime written = AlarmFileTime();

                if (written > _alarmFileSeen)
                {
                    _alarmFileSeen = written;
                    (string who, string why) = ReadAlarmFile();

                    if (who != null && !who.Equals(_characterName, StringComparison.OrdinalIgnoreCase))
                    {
                        Alarm($"partner {who}: {why}", null, 0, false);

                        if (g.LogOut)
                        {
                            return;
                        }
                    }
                }
            }

            if (g.Attack && p.HitsMax > 0)
            {
                if (_lastHits >= 0 && p.Hits < _lastHits)
                {
                    Mobile near = NearestStranger(rules, 12);
                    Alarm($"hit points went down from {_lastHits} to {p.Hits}: attacked?", near, near?.Serial ?? 0, true);
                }

                _lastHits = p.Hits;
            }

            // runes are never used up or moved by the agent, so one that goes missing was taken
            foreach (uint serial in g.WatchItems)
            {
                Item item = _world.Items.Get(serial);

                if (item != null && !item.IsDestroyed && IsCarried(item))
                {
                    _seenCarried.Add(serial);
                }
                else if (_seenCarried.Remove(serial))
                {
                    Mobile near = NearestStranger(rules, 12);
                    Alarm($"{Hex(serial)} is gone from the backpack: stolen?", near, near?.Serial ?? 0, true);
                }
            }

            TradingGump trade = FindTrade();

            if (trade != null)
            {
                Mobile who = _world.Mobiles.Get(trade.LocalSerial);

                if (who == null || !IsPartner(who, rules))
                {
                    GameActions.CancelTrade(trade.ID1);
                    Alarm($"{Describe(who, trade.LocalSerial)} opened a trade", who, trade.LocalSerial, true);
                }
            }

            // someone standing close instead of walking past may be snooping or stealing
            var near3 = new List<uint>();

            foreach (Mobile m in _world.Mobiles.Values)
            {
                if (m == p || m.IsDestroyed || !(m.IsHuman || m.IsDead) || IsFriendly(m, rules) || m.Distance > g.LoiterRange)
                {
                    continue;
                }

                near3.Add(m.Serial);

                if (!_nearSince.TryGetValue(m.Serial, out DateTime since))
                {
                    _nearSince[m.Serial] = now;
                }
                else if ((now - since).TotalSeconds > g.LoiterSeconds)
                {
                    Alarm($"{Describe(m, m.Serial)} stood within {g.LoiterRange} tiles for over {g.LoiterSeconds} seconds", m, m.Serial, true);
                }
            }

            if (_nearSince.Count > near3.Count)
            {
                var gone = new List<uint>();

                foreach (uint serial in _nearSince.Keys)
                {
                    if (!near3.Contains(serial))
                    {
                        gone.Add(serial);
                    }
                }

                foreach (uint serial in gone)
                {
                    _nearSince.Remove(serial);
                }
            }
        }

        // anyone but the user's own characters and the local townsfolk speaking nearby
        private void CheckTalk(MessageEventArgs e)
        {
            Rules rules = _rules;
            GuardRules g = rules?.Guard;

            if (g == null || _logoutRequest != null)
            {
                return;
            }

            if (e.Parent is Mobile m)
            {
                if (m == _world.Player || IsFriendly(m, rules))
                {
                    return;
                }

                switch (e.Type)
                {
                    case MessageType.Label:   // a name from a single click
                    case MessageType.Party:
                    case MessageType.Guild:
                    case MessageType.Alliance:
                    case MessageType.Command:
                        return;
                }

                // a guild tag ("[title, ABBR]") comes after the name when a player is single-clicked, as ordinary
                // speech: not someone talking (the user, 2026-11-02, after two false alarms)
                string text = e.Text ?? "";

                if (text.Length > 1 && text[0] == '[' && text[text.Length - 1] == ']')
                {
                    return;
                }

                if (g.Talk)
                {
                    Alarm($"{Describe(m, m.Serial)} said \"{e.Text}\"", m, m.Serial, true);
                }

                return;
            }

            if (e.Parent != null)
            {
                return; // an item, such as the trash barrel
            }

            string lower = e.Text.ToLowerInvariant();

            // "You see X attacking you!", "You notice X trying to steal from you"
            if (g.Attack && (lower.Contains("attacking you") || lower.Contains("you notice")))
            {
                Mobile near = NearestStranger(rules, 12);
                Alarm($"the server said \"{e.Text}\"", near, near?.Serial ?? 0, true);

                return;
            }

            // speech from someone the client doesn't know, other than the server itself
            if (g.Talk && e.Type != MessageType.System && e.Type != MessageType.Label && !string.IsNullOrEmpty(e.Name)
                && !e.Name.Equals("System", StringComparison.OrdinalIgnoreCase) && !rules.Partners.Contains(e.Name) && !g.NpcNames.Contains(e.Name))
            {
                Alarm($"{e.Name} said \"{e.Text}\"", null, 0, true);
            }
        }

        // a partner by name, or by serial (a mobile that has just come back into view may not have its name yet)
        private static bool IsPartner(Mobile m, Rules rules)
        {
            return m != null && (rules.Partners.Contains(m.Name ?? "") || rules.Partners.Contains(Hex(m.Serial)));
        }

        private bool IsFriendly(Mobile m, Rules rules)
        {
            string name = m.Name ?? "";

            return IsPartner(m, rules) || LoadLearnedNpcs().Contains(m.Serial) || rules.Guard != null && (rules.Guard.NpcSerials.Contains(m.Serial) || rules.Guard.NpcNames.Contains(name));
        }

        // the nearest person who isn't a partner or one of the townsfolk: the likely culprit
        private Mobile NearestStranger(Rules rules, int range)
        {
            Mobile best = null;

            foreach (Mobile m in _world.Mobiles.Values)
            {
                if (m != _world.Player && !m.IsDestroyed && (m.IsHuman || m.IsDead) && !IsFriendly(m, rules) && m.Distance <= range && (best == null || m.Distance < best.Distance))
                {
                    best = m;
                }
            }

            return best;
        }

        private static string Describe(Mobile m, uint serial) => $"{(string.IsNullOrEmpty(m?.Name) ? "someone" : m.Name)} ({Hex(serial)})";

        private static string AlarmPath() => Path.Combine(CUOEnviroment.ExecutablePath, "Agent", "alarm.json");

        private static DateTime AlarmFileTime()
        {
            try
            {
                string path = AlarmPath();

                return File.Exists(path) ? File.GetLastWriteTimeUtc(path) : DateTime.MinValue;
            }
            catch (IOException)
            {
                return DateTime.MinValue;
            }
        }

        private static (string Who, string Why) ReadAlarmFile()
        {
            try
            {
                using JsonDocument doc = JsonDocument.Parse(File.ReadAllBytes(AlarmPath()));
                JsonElement root = doc.RootElement;

                return
                (
                    root.GetProperty("character").GetString(),
                    root.GetProperty("reason").GetString()
                );
            }
            catch (Exception)
            {
                return (null, null);
            }
        }

        // the guard went off: stop work at once, note who it was, and tell the partner's client. The agent then gets
        // the character away and hides (or the bridge hides him itself if nobody does); with "onAlarm": "logout"
        // in the rules the character logs out instead.
        private void Alarm(string reason, Mobile threat, uint threatSerial, bool tellPartner)
        {
            string line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {_characterName}: {reason}";

            if (line.Substring(20) != _lastLogged)
            {
                _lastLogged = line.Substring(20);
                AppendAlarmLog(line);
            }

            if (_logoutRequest != null)
            {
                return;
            }

            if (_alarm != null)
            {
                return; // already dealing with one; the log has the rest
            }

            GuardRules g = _rules?.Guard;
            DateTime now = DateTime.UtcNow;
            _alarm = $"{DateTime.Now:HH:mm:ss} {reason}";
            _alarmAt = now;
            _evading = false;
            _nextAutoHide = now.AddSeconds(g?.HideAfter ?? 5);

            if (threat != null || threatSerial != 0)
            {
                _threat = new Threat
                {
                    Serial = threatSerial,
                    Name = threat?.Name,
                    X = threat?.X ?? _world.Player.X,
                    Y = threat?.Y ?? _world.Player.Y,
                    Seen = now
                };
            }

            Log.Warn($"Agent bridge guard: {_alarm}");

            // stop whatever was going on: a walk, a target cursor, an item in hand
            _world.Player.Pathfinder.StopAutoWalk();
            CancelTarget();
            ReleaseHeldItem();

            if (tellPartner)
            {
                WriteAlarmFile(reason);
            }

            if (g != null && g.LogOut)
            {
                _logoutRequest = reason;
            }
        }

        private void WriteAlarmFile(string reason)
        {
            try
            {
                File.WriteAllBytes
                (
                    AlarmPath(),
                    Json
                    (
                        w =>
                        {
                            w.WriteStartObject();
                            w.WriteString("time", DateTime.Now.ToString("s", CultureInfo.InvariantCulture));
                            w.WriteString("character", _characterName);
                            w.WriteString("reason", reason);
                            w.WriteEndObject();
                        }
                    )
                );

                _alarmFileSeen = AlarmFileTime(); // this bridge's own alarm isn't news to it
            }
            catch (Exception ex)
            {
                Log.Error($"Agent bridge guard: could not write the alarm: {ex.Message}");
            }
        }

        private void AppendAlarmLog(string line)
        {
            try
            {
                string folder = FileSystemHelper.CreateFolderIfNotExists(CUOEnviroment.ExecutablePath, "Agent");
                File.AppendAllText(Path.Combine(folder, "alarms.log"), line + Environment.NewLine);
            }
            catch (Exception ex)
            {
                Log.Error($"Agent bridge guard: could not log the alarm: {ex.Message}");
            }
        }

        // on the listener thread: normal work stops while the guard's alarm is on
        private void CheckNoAlarm()
        {
            string alarm = _alarm;

            if (alarm != null)
            {
                throw new BridgeException(409, $"alarm: {alarm}");
            }
        }

        private void WriteGuard(Utf8JsonWriter w, bool on)
        {
            w.WriteStartObject();
            WriteGuardFields(w);
            w.WriteEndObject();
        }

        private void WriteGuardFields(Utf8JsonWriter w)
        {
            DateTime now = DateTime.UtcNow;

            w.WriteStartObject("guard");
            w.WriteBoolean("on", _guardOn);

            if (_alarm != null)
            {
                w.WriteStartObject("alarm");
                w.WriteString("reason", _alarm);
                w.WriteNumber("seconds", Math.Round((now - _alarmAt).TotalSeconds));
                w.WriteBoolean("evading", _evading);

                if (_threat != null)
                {
                    Mobile m = _threat.Serial != 0 ? _world.Mobiles.Get(_threat.Serial) : null;

                    w.WriteStartObject("threat");
                    w.WriteString("serial", Hex(_threat.Serial));
                    w.WriteString("name", _threat.Name);
                    w.WriteNumber("x", _threat.X);
                    w.WriteNumber("y", _threat.Y);
                    w.WriteBoolean("visible", m != null && !m.IsDestroyed);
                    w.WriteNumber("secondsSinceSeen", Math.Round((now - _threat.Seen).TotalSeconds));
                    w.WriteEndObject();
                }

                w.WriteEndObject();
            }

            GuardRules g = _rules?.Guard;

            if (g != null)
            {
                w.WriteStartArray("watching");

                foreach (uint serial in g.WatchItems)
                {
                    w.WriteStartObject();
                    w.WriteString("serial", Hex(serial));
                    w.WriteBoolean("seen", _seenCarried.Contains(serial));
                    w.WriteEndObject();
                }

                w.WriteEndArray();
            }

            w.WriteStartArray("near");

            foreach (KeyValuePair<uint, DateTime> pair in _nearSince)
            {
                w.WriteStartObject();
                w.WriteString("serial", Hex(pair.Key));
                w.WriteString("name", _world.Mobiles.Get(pair.Key)?.Name);
                w.WriteNumber("seconds", Math.Round((now - pair.Value).TotalSeconds, 1));
                w.WriteEndObject();
            }

            w.WriteEndArray();
            w.WriteEndObject();
        }

        // uses a skill the rules allow (21 is Hiding)
        // a skill, and for one that asks for a target, the target: only ever one of the character's own mounts from
        // the rules (Animal Taming on a horse that has gone wild, the user 2026-11-02)
        // keepCursor: a skill that asks for targets (Provocation) leaves its cursor up, and /target answers it
        private byte[] UseSkill(int skill, uint target = 0, bool keepCursor = false)
        {
            Rules rules = RequireRules();
            CheckNoPendingAim();

            if (!rules.Skills.Contains(skill))
            {
                throw new BridgeException(403, "the rules don't allow that skill");
            }

            if (target != 0 && !rules.Mounts.Contains(target))
            {
                throw new BridgeException(403, "a skill is only aimed at one of the mounts in the rules");
            }

            if (_alarm != null)
            {
                _evading = true;
            }

            WaitForActionSlot();

            long before = OnGame
            (
                () =>
                {
                    if (target != 0)
                    {
                        Mobile m = _world.Mobiles.Get(target) ?? throw new BridgeException(404, "that mount isn't nearby");

                        if (m.Distance > REACH)
                        {
                            throw new BridgeException(409, $"too far away ({m.Distance} tiles, reach is {REACH}); walk closer first");
                        }
                    }

                    if (_world.TargetManager.IsTargeting)
                    {
                        _world.TargetManager.CancelTarget();
                    }

                    LogAction($"skill {skill}", 0);
                    long id = _lastMessageId;
                    GameActions.UseSkill(skill);

                    return id;
                }
            );

            WaitFor(() => HasSystemMessageAfter(before) || _world.TargetManager.IsTargeting || skill == HIDING && _world.Player.IsHidden, SKILL_TIMEOUT);

            if (target != 0)
            {
                WaitFor(() => _world.TargetManager.IsTargeting, 1000); // "Tame which animal?" can come a moment before the cursor
            }

            if (OnGame(() => _world.TargetManager.IsTargeting))
            {
                if (target == 0 && keepCursor)
                {
                    return OnGame
                    (
                        () => Json
                        (
                            w =>
                            {
                                w.WriteStartObject();
                                w.WriteBoolean("targeting", true);
                                WriteMessagesSince(w, before, 0);
                                w.WriteEndObject();
                            }
                        )
                    );
                }

                if (target == 0)
                {
                    OnGame(CancelTarget);

                    throw new BridgeException(400, "that skill wants a target; give target=");
                }

                Aim(rules);

                long aimed = OnGame
                (
                    () =>
                    {
                        LogAction("target", target);
                        long id = _lastMessageId;
                        _world.TargetManager.Target(target);

                        return id;
                    }
                );

                // taming answers at once ("You start to tame the creature.") and settles over the next seconds,
                // which the caller reads from /messages
                if (!WaitFor(() => HasSystemMessageAfter(aimed) || HasMessageFrom(_world.Player.Serial, aimed), SKILL_TIMEOUT))
                {
                    OnGame(CancelTarget);
                    Halt($"no answer after aiming skill {skill} at {Hex(target)}");
                }

                OnGame(CancelTarget);
                PaceFromNow();
            }

            Thread.Sleep(SETTLE_TIME);

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        w.WriteStartObject();
                        w.WriteBoolean("hidden", _world.Player.IsHidden);
                        WriteMessagesSince(w, before, 0);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // double-clicks the character himself, which gets off a mount
        private byte[] Dismount()
        {
            Rules rules = RequireRules();

            if (rules.Mounts.Count == 0)
            {
                throw new BridgeException(403, "the rules name no mounts");
            }

            WaitForActionSlot();

            long before = OnGame
            (
                () =>
                {
                    PlayerMobile p = _world.Player;

                    if (p.FindItemByLayer(Layer.Mount) == null)
                    {
                        throw new BridgeException(409, "not riding");
                    }

                    LogAction("dismount (double-click self)", p.Serial);
                    long id = _lastMessageId;
                    GameActions.DoubleClick(_world, p.Serial);

                    return id;
                }
            );

            WaitFor(() => _world.Player.FindItemByLayer(Layer.Mount) == null || HasSystemMessageAfter(before), MOUNT_TIMEOUT);
            Thread.Sleep(SETTLE_TIME);

            return OnGame(() => Json(w => WriteMountResult(w, before)));
        }

        // double-clicks one of the character's own mounts named in the rules, to ride it
        private byte[] Mount(uint serial)
        {
            Rules rules = RequireRules();

            if (!rules.Mounts.Contains(serial))
            {
                throw new BridgeException(403, "that isn't one of the mounts in the rules");
            }

            WaitForActionSlot();

            long before = OnGame
            (
                () =>
                {
                    PlayerMobile p = _world.Player;

                    if (p.FindItemByLayer(Layer.Mount) != null)
                    {
                        throw new BridgeException(409, "already riding");
                    }

                    Mobile m = _world.Mobiles.Get(serial) ?? throw new BridgeException(404, "that mount isn't nearby");

                    if (m.Distance > REACH)
                    {
                        throw new BridgeException(409, $"too far away ({m.Distance} tiles, reach is {REACH}); walk closer first");
                    }

                    LogAction("mount (double-click)", serial);
                    long id = _lastMessageId;
                    GameActions.DoubleClick(_world, serial);

                    return id;
                }
            );

            WaitFor(() => _world.Player.FindItemByLayer(Layer.Mount) != null || HasSystemMessageAfter(before), MOUNT_TIMEOUT);
            Thread.Sleep(SETTLE_TIME);

            return OnGame(() => Json(w => WriteMountResult(w, before)));
        }

        private void WriteMountResult(Utf8JsonWriter w, long before)
        {
            w.WriteStartObject();
            w.WriteBoolean("mounted", _world.Player.FindItemByLayer(Layer.Mount) != null);
            WriteMessagesSince(w, before, 0);
            w.WriteEndObject();
        }

        private void WriteTrade(Utf8JsonWriter w)
        {
            TradingGump gump = FindTrade();

            if (gump == null)
            {
                w.WriteNull("trade");

                return;
            }

            w.WriteStartObject("trade");
            w.WriteString("partner", Hex(gump.LocalSerial));
            w.WriteString("partnerName", _world.Mobiles.Get(gump.LocalSerial)?.Name);
            w.WriteBoolean("imAccepting", gump.ImAccepting);
            w.WriteBoolean("heIsAccepting", gump.HeIsAccepting);

            foreach ((string key, uint box) in new[] { ("mine", gump.ID1), ("his", gump.ID2) })
            {
                w.WriteStartArray(key);
                Item container = _world.Items.Get(box);

                for (LinkedObject i = container?.Items; i != null; i = i.Next)
                {
                    WriteItem(w, (Item)i);
                }

                w.WriteEndArray();
            }

            w.WriteEndObject();
        }

        // the ground and statics around the character, as the client has them (for finding rock to mine)
        private void WriteTiles(Utf8JsonWriter w, int range)
        {
            PlayerMobile p = _world.Player;
            var tileData = Client.Game.UO.FileManager.TileData;

            w.WriteStartObject();
            w.WriteNumber("x", p.X);
            w.WriteNumber("y", p.Y);
            w.WriteStartArray("tiles");

            for (int y = p.Y - range; y <= p.Y + range; y++)
            {
                for (int x = p.X - range; x <= p.X + range; x++)
                {
                    w.WriteStartObject();
                    w.WriteNumber("x", x);
                    w.WriteNumber("y", y);
                    w.WriteStartArray("statics");

                    Land land = null;

                    for (GameObject o = _world.Map.GetTile(x, y); o != null; o = o.TNext)
                    {
                        if (o is Land l)
                        {
                            land = l;
                        }
                        else if (o is Static s)
                        {
                            w.WriteStartObject();
                            w.WriteString("graphic", Hex(s.Graphic));
                            w.WriteNumber("z", s.Z);
                            w.WriteString("name", s.Graphic < tileData.StaticData.Length ? tileData.StaticData[s.Graphic].Name : null);
                            w.WriteEndObject();
                        }
                    }

                    w.WriteEndArray();

                    if (land != null)
                    {
                        w.WriteString("land", Hex(land.Graphic));
                        w.WriteNumber("landZ", land.Z);
                        w.WriteString("landName", land.Graphic < tileData.LandData.Length ? tileData.LandData[land.Graphic].Name : null);
                    }

                    w.WriteEndObject();
                }
            }

            w.WriteEndArray();
            w.WriteEndObject();
        }

        // ---- rules, on the game thread unless noted ----

        // returns the item's outermost container on the ground, or null when the character carries it
        private Item CheckReachable(Item item, Rules rules, string what)
        {
            // never-touch kinds are decoration lying on the floor; the same kind in a container is fair game
            if (item.OnGround && rules.NeverTouch.Contains(item.Graphic))
            {
                throw new BridgeException(403, $"the agent may never {what} that kind of item on the floor");
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

        private bool IsCarried(Item item)
        {
            for (uint parent = item.Container; SerialHelper.IsValid(parent);)
            {
                if (parent == _world.Player.Serial)
                {
                    return true;
                }

                if (_world.Get(parent) is not Item container)
                {
                    return false;
                }

                parent = container.Container;
            }

            return false;
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
            // out in the world people pass by all the time; there the guard deals with them instead
            if (!rules.PauseForPeople)
            {
                return;
            }

            foreach (Mobile m in _world.Mobiles.Values)
            {
                if (m == _world.Player || m.IsDestroyed || !(m.IsHuman || m.IsDead) || rules.IgnorePeople.Contains(m.Name ?? "") || IsPartner(m, rules))
                {
                    continue;
                }

                if (rules.Contains(_world.MapIndex, m.X, m.Y, m.Z))
                {
                    throw new BridgeException(409, $"paused: {(string.IsNullOrEmpty(m.Name) ? "someone" : m.Name)} is in the agent's area");
                }
            }
        }

        // on the listener thread; reloads the rules when the file changes. A character's own
        // Agent/rules-<character>.json comes first, then the shared Agent/rules.json.
        private Rules RequireRules()
        {
            string folder = Path.Combine(CUOEnviroment.ExecutablePath, "Agent");
            string own = "rules-" + SafeFileName(_characterName) + ".json";
            string name = File.Exists(Path.Combine(folder, own)) ? own : "rules.json";
            string path = Path.Combine(folder, name);

            if (!File.Exists(path))
            {
                throw new BridgeException(403, $"actions are off until Agent/{own} or Agent/rules.json sets the agent's area");
            }

            DateTime time = File.GetLastWriteTimeUtc(path);

            if (_rules == null || time != _rulesTime || name != _rulesName)
            {
                try
                {
                    Rules rules = Rules.Parse(File.ReadAllBytes(path));
                    rules.FileName = name;
                    _rules = rules;
                    _rulesTime = time;
                    _rulesName = name;
                }
                catch (Exception ex)
                {
                    _rules = null;

                    throw new BridgeException(403, $"Agent/{name} is not valid: {ex.Message}");
                }
            }

            return _rules;
        }

        private static string SafeFileName(string name)
        {
            name = string.IsNullOrEmpty(name) ? "unknown" : name;

            foreach (char c in Path.GetInvalidFileNameChars())
            {
                name = name.Replace(c, '_');
            }

            return name;
        }

        // on the listener thread: waits for this action's turn, then books the gap before the next one.
        // The same action repeated straight away (another stroke of the shovel at the same rock) only waits the
        // short "repeat" gap when the rules give one; anything else after it still waits a full gap.
        private bool WaitForActionSlot(string kind = null)
        {
            CheckNotHalted();

            Rules pacing = TryRules() ?? Rules.Defaults;
            bool repeat = kind != null && kind == _lastKind && pacing.RepeatMax > 0 && (DateTime.UtcNow - _lastKindAt).TotalMilliseconds < REPEAT_WINDOW;

            if (repeat)
            {
                Thread.Sleep(_random.Next(pacing.RepeatMin, pacing.RepeatMax + 1));
            }
            else
            {
                int wait = (int)(_nextAction - DateTime.UtcNow).TotalMilliseconds;

                if (wait > 0)
                {
                    Thread.Sleep(wait);
                }
            }

            while (OnGame(IsSaving))
            {
                Thread.Sleep(500);
            }

            bool takeBreak = !repeat && ++_burstCount >= pacing.Burst;

            if (takeBreak)
            {
                _burstCount = 0;
            }

            int gap = takeBreak ? _random.Next(pacing.BreakMin, pacing.BreakMax + 1) : _random.Next(pacing.GapMin, pacing.GapMax + 1);
            _nextAction = DateTime.UtcNow.AddMilliseconds(gap);
            _lastKind = kind;
            _lastKindAt = DateTime.UtcNow;

            return repeat;
        }

        // on the listener thread: a person takes a moment to aim once the target cursor shows
        private void Aim(Rules rules, bool repeat = false)
        {
            if (repeat && rules.RepeatAimMax > 0)
            {
                Thread.Sleep(_random.Next(rules.RepeatAimMin, rules.RepeatAimMax + 1));
            }
            else if (rules.AimMax > 0)
            {
                Thread.Sleep(_random.Next(rules.AimMin, rules.AimMax + 1));
            }
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

        // on the listener thread: an action that can bring a cursor of its own (a skill, a key, "remove thyself") waits
        // until a spell cast with wait=0 has had its cursor aimed, or the two cursors would get mixed up (409: try again)
        private void CheckNoPendingAim()
        {
            if (OnGame(() => _aimTarget != 0 && DateTime.UtcNow <= _aimUntil))
            {
                throw new BridgeException(409, "a spell's target cursor is still to come");
            }
        }

        // on the listener thread
        private void CheckNotHalted()
        {
            if (_takenOver != null || _userActed != null)
            {
                throw new BridgeException(423, $"the user took over ({_takenOver ?? _userActed}); resume when they hand the character back");
            }

            if (_halted != null)
            {
                throw new BridgeException(423, $"stopped because the server went quiet ({_halted}); check the game, then resume");
            }
        }

        // on the listener thread: the server didn't answer, so stop everything until told to resume
        private void Halt(string why)
        {
            string alarm = _alarm;

            if (alarm != null)
            {
                throw new BridgeException(409, $"alarm: {alarm} (stopped {why})");
            }

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

        // waits for an answer; while the world saves the server answers nothing, so the clock restarts until it's done
        private bool WaitFor(Func<bool> condition, int timeout)
        {
            DateTime end = DateTime.UtcNow.AddMilliseconds(timeout);

            while (true)
            {
                (bool met, bool saving) = OnGame(() => (condition(), IsSaving()));

                if (met)
                {
                    return true;
                }

                if (saving)
                {
                    end = DateTime.UtcNow.AddMilliseconds(timeout);
                }
                else if (DateTime.UtcNow >= end)
                {
                    return false;
                }

                Thread.Sleep(POLL_INTERVAL);
            }
        }

        // on the game thread
        private bool IsSaving() => _saving && (DateTime.Now - _saveStarted).TotalMinutes < SAVE_LIMIT;

        // on the listener thread: what was sent and when, to line up with the server's "You must wait"
        private void LogAction(string what, uint serial)
        {
            _actions.Enqueue((DateTime.Now, what, serial));

            while (_actions.Count > ACTION_LOG)
            {
                _actions.Dequeue();
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

            if (_takenOver != null)
            {
                w.WriteString("takenOver", _takenOver);
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
            w.WriteBoolean("mounted", p.FindItemByLayer(Layer.Mount) != null);
            w.WriteBoolean("hidden", p.IsHidden);
            w.WriteBoolean("dead", p.IsDead);
            w.WriteBoolean("paralyzed", p.IsParalyzed);
            w.WriteBoolean("poisoned", p.IsPoisoned);
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

            Item bank = p.FindItemByLayer(Layer.Bank);

            if (bank != null)
            {
                w.WriteString("bank", Hex(bank.Serial));
            }

            WriteTrade(w);
            WriteGuardFields(w);
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

                // another creature's health comes from the server scaled (often out of 25 or 100): the share is what counts
                if (mobile.HitsMax > 0)
                {
                    w.WriteNumber("hits", mobile.Hits);
                    w.WriteNumber("hitsMax", mobile.HitsMax);
                }

                w.WriteBoolean("warMode", mobile.InWarMode);
                w.WriteBoolean("paralyzed", mobile.IsParalyzed);
                w.WriteBoolean("poisoned", mobile.IsPoisoned);
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
            public string FileName;
            public int Map = -1;
            public readonly List<Box> Areas = new List<Box>();
            public readonly HashSet<uint> OffLimits = new HashSet<uint>();
            public readonly HashSet<ushort> NeverTouch = new HashSet<ushort>();
            public readonly HashSet<string> IgnorePeople = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            public readonly HashSet<string> Partners = new HashSet<string>(StringComparer.OrdinalIgnoreCase); // the user's own characters: trades go only to them, and the guard ignores them
            public readonly HashSet<ushort> UseFromBackpack = new HashSet<ushort>(); // tools that may be used without holding them (scissors)
            public readonly HashSet<ushort> DropOnGround = new HashSet<ushort>(); // carried kinds that may be put down at the character's feet (ore, when a dig overloads the miner)
            public readonly HashSet<ushort> UseOnGround = new HashSet<ushort>(); // kinds that may be double-clicked where they lie, within reach and inside the area (a pile of bandages)
            public readonly HashSet<string> Patients = new HashSet<string>(StringComparer.OrdinalIgnoreCase); // the user's own characters an item's cursor may be aimed at (bandages), by name or serial
            public readonly HashSet<string> Say = new HashSet<string>(StringComparer.OrdinalIgnoreCase); // the only words the character may say ("bank")
            public readonly HashSet<int> Spells = new HashSet<int>(); // the only spells it may cast (32 is Recall)
            public readonly HashSet<int> Skills = new HashSet<int>(); // the only skills it may use (21 is Hiding)
            public readonly HashSet<uint> Mounts = new HashSet<uint>(); // its own horses, to get on and off
            public readonly HashSet<uint> Doors = new HashSet<uint>(); // doors it may open and close (double-click) and aim a key at
            public readonly HashSet<uint> Keys = new HashSet<uint>(); // key rings it may use where they hang (locked down by a door)
            public bool Fight; // may aim skills and spells at creatures anybody may attack, and at itself, and walk without waiting
            public bool HandOver; // a command the user gives themselves (a step, a spell, a skill, a click, a target) stops all actions until /resume
            public bool PauseForPeople = true;
            public GuardRules Guard;

            // a random gap between actions, and a longer break after every Burst actions (milliseconds)
            public int GapMin = 1200, GapMax = 2000, Burst = 5, BreakMin = 3000, BreakMax = 5000;

            // between a target cursor appearing and the click on the target (milliseconds), as a person takes to aim;
            // also before answering a menu or gump when given (AimGiven), else about half a second
            public int AimMin, AimMax;
            public bool AimGiven;

            // the same stroke repeated (digging on at the same rock): the gap and the aim, instead of the above
            public int RepeatMin, RepeatMax, RepeatAimMin, RepeatAimMax;

            public static readonly Rules Defaults = new Rules();

            public bool Contains(int map, int x, int y, int z) => AreaAt(map, x, y, z) != null;

            // a spot to aim at (a rock face, a forge) only has to lie inside an area; its height doesn't matter
            public bool ContainsSpot(int map, int x, int y) => AreaAt(map, x, y, 0, true) != null;

            public Box AreaAt(int map, int x, int y, int z, bool anyHeight = false)
            {
                if (Map >= 0 && map != Map)
                {
                    return null;
                }

                foreach (Box box in Areas)
                {
                    if (box.Contains(x, y, anyHeight ? box.ZMin : z))
                    {
                        return box;
                    }
                }

                return null;
            }

            // { "map": 0, "area": [x1, y1, x2, y2], "z": [min, max], "offLimits": ["0x..."], "neverTouch": ["0x1766"], "ignorePeople": [] }
            // or several areas: "areas": [{ "name": "forge", "box": [x1, y1, x2, y2], "z": [min, max] }, ...]
            public static Rules Parse(byte[] json)
            {
                using JsonDocument doc = JsonDocument.Parse
                (
                    json,
                    new JsonDocumentOptions { AllowTrailingCommas = true, CommentHandling = JsonCommentHandling.Skip }
                );

                JsonElement root = doc.RootElement;
                var rules = new Rules();

                if (root.TryGetProperty("area", out JsonElement area))
                {
                    rules.Areas.Add(Box.Parse("area", area, root.TryGetProperty("z", out JsonElement z) ? z : default));
                }

                if (root.TryGetProperty("areas", out JsonElement areas))
                {
                    foreach (JsonElement e in areas.EnumerateArray())
                    {
                        rules.Areas.Add
                        (
                            Box.Parse
                            (
                                e.TryGetProperty("name", out JsonElement name) ? name.GetString() : $"area {rules.Areas.Count + 1}",
                                e.GetProperty("box"),
                                e.TryGetProperty("z", out JsonElement boxZ) ? boxZ : default
                            )
                        );
                    }
                }

                if (rules.Areas.Count == 0)
                {
                    throw new FormatException("no area: give \"area\" or \"areas\"");
                }

                if (root.TryGetProperty("map", out JsonElement map))
                {
                    rules.Map = map.GetInt32();
                }

                ReadNumbers(root, "offLimits", n => rules.OffLimits.Add(n));
                ReadNumbers(root, "neverTouch", n => rules.NeverTouch.Add((ushort)n));
                ReadNumbers(root, "useFromBackpack", n => rules.UseFromBackpack.Add((ushort)n));
                ReadNumbers(root, "dropOnGround", n => rules.DropOnGround.Add((ushort)n));
                ReadNumbers(root, "useOnGround", n => rules.UseOnGround.Add((ushort)n));
                ReadStrings(root, "patients", rules.Patients);
                ReadStrings(root, "ignorePeople", rules.IgnorePeople);
                ReadStrings(root, "partners", rules.Partners);
                ReadStrings(root, "say", rules.Say);

                if (root.TryGetProperty("spells", out JsonElement spells))
                {
                    foreach (JsonElement e in spells.EnumerateArray())
                    {
                        rules.Spells.Add(e.GetInt32());
                    }
                }

                if (root.TryGetProperty("skills", out JsonElement skills))
                {
                    foreach (JsonElement e in skills.EnumerateArray())
                    {
                        rules.Skills.Add(e.GetInt32());
                    }
                }

                ReadNumbers(root, "mounts", n => rules.Mounts.Add(n));
                ReadNumbers(root, "doors", n => rules.Doors.Add(n));
                ReadNumbers(root, "keys", n => rules.Keys.Add(n));

                if (root.TryGetProperty("fight", out JsonElement fight))
                {
                    rules.Fight = fight.GetBoolean();
                }

                if (root.TryGetProperty("handOver", out JsonElement handOver))
                {
                    rules.HandOver = handOver.GetBoolean();
                }

                if (root.TryGetProperty("pauseForPeople", out JsonElement pause))
                {
                    rules.PauseForPeople = pause.GetBoolean();
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

                    if (pacing.TryGetProperty("break", out JsonElement longBreak))
                    {
                        rules.BreakMin = Math.Max(rules.GapMin, longBreak[0].GetInt32());
                        rules.BreakMax = Math.Max(rules.BreakMin, longBreak[1].GetInt32());
                    }

                    if (pacing.TryGetProperty("aim", out JsonElement aim))
                    {
                        rules.AimMin = Math.Clamp(aim[0].GetInt32(), 0, 2500);
                        rules.AimMax = Math.Clamp(aim[1].GetInt32(), rules.AimMin, 2500);
                        rules.AimGiven = true;
                    }

                    // never quicker than 200 ms: the server's own swing time does the rest
                    if (pacing.TryGetProperty("repeat", out JsonElement repeatGap))
                    {
                        rules.RepeatMin = Math.Clamp(repeatGap[0].GetInt32(), 200, 5000);
                        rules.RepeatMax = Math.Clamp(repeatGap[1].GetInt32(), rules.RepeatMin, 5000);
                    }

                    if (pacing.TryGetProperty("repeatAim", out JsonElement repeatAim))
                    {
                        rules.RepeatAimMin = Math.Clamp(repeatAim[0].GetInt32(), 0, 2500);
                        rules.RepeatAimMax = Math.Clamp(repeatAim[1].GetInt32(), rules.RepeatAimMin, 2500);
                    }
                }

                // "guard": { "talk": true, "loiter": [3, 10], "attack": true, "watchItems": ["0x..."], "npcs": ["0x...", "Name"] }
                if (root.TryGetProperty("guard", out JsonElement guard))
                {
                    var g = new GuardRules();

                    if (guard.TryGetProperty("talk", out JsonElement talk))
                    {
                        g.Talk = talk.GetBoolean();
                    }

                    if (guard.TryGetProperty("loiter", out JsonElement loiter))
                    {
                        g.LoiterRange = Math.Clamp(loiter[0].GetInt32(), 1, 18);
                        g.LoiterSeconds = Math.Clamp(loiter[1].GetInt32(), 1, 600);
                    }

                    if (guard.TryGetProperty("attack", out JsonElement attack))
                    {
                        g.Attack = attack.GetBoolean();
                    }

                    if (guard.TryGetProperty("onAlarm", out JsonElement onAlarm))
                    {
                        g.LogOut = onAlarm.GetString() == "logout";
                    }

                    if (guard.TryGetProperty("hideAfter", out JsonElement hideAfter))
                    {
                        g.HideAfter = Math.Clamp(hideAfter.GetInt32(), 1, 120);
                    }

                    ReadNumbers(guard, "watchItems", n => g.WatchItems.Add(n));

                    if (guard.TryGetProperty("fidgets", out JsonElement fidgets))
                    {
                        foreach (JsonElement e in fidgets.EnumerateArray())
                        {
                            g.Fidgets.Add((ushort)e.GetInt32());
                        }
                    }

                    if (guard.TryGetProperty("npcs", out JsonElement npcs))
                    {
                        foreach (JsonElement e in npcs.EnumerateArray())
                        {
                            string s = e.GetString() ?? "";

                            if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase) && TryParseSerial(s, out uint serial))
                            {
                                g.NpcSerials.Add(serial);
                            }
                            else
                            {
                                g.NpcNames.Add(s);
                            }
                        }
                    }

                    rules.Guard = g;
                }

                return rules;
            }

            private static void ReadNumbers(JsonElement parent, string key, Action<uint> add)
            {
                if (parent.TryGetProperty(key, out JsonElement list))
                {
                    foreach (JsonElement e in list.EnumerateArray())
                    {
                        add(ParseNumber(e.GetString()));
                    }
                }
            }

            private static void ReadStrings(JsonElement parent, string key, HashSet<string> into)
            {
                if (parent.TryGetProperty(key, out JsonElement list))
                {
                    foreach (JsonElement e in list.EnumerateArray())
                    {
                        into.Add(e.GetString());
                    }
                }
            }

            public void Write(Utf8JsonWriter w)
            {
                w.WriteStartObject();
                w.WriteString("file", FileName);
                w.WriteNumber("map", Map);
                w.WriteStartArray("areas");

                foreach (Box box in Areas)
                {
                    box.Write(w);
                }

                w.WriteEndArray();
                w.WriteBoolean("pauseForPeople", PauseForPeople);
                WriteList(w, "offLimits", OffLimits, s => Hex(s));
                WriteList(w, "neverTouch", NeverTouch, g => Hex(g));
                WriteList(w, "ignorePeople", IgnorePeople, s => s);
                WriteList(w, "partners", Partners, s => s);
                WriteList(w, "useFromBackpack", UseFromBackpack, g => Hex(g));
                WriteList(w, "dropOnGround", DropOnGround, g => Hex(g));
                WriteList(w, "useOnGround", UseOnGround, g => Hex(g));
                WriteList(w, "patients", Patients, s => s);
                WriteList(w, "say", Say, s => s);
                w.WriteStartArray("spells");

                foreach (int spell in Spells)
                {
                    w.WriteNumberValue(spell);
                }

                w.WriteEndArray();
                w.WriteStartArray("skills");

                foreach (int skill in Skills)
                {
                    w.WriteNumberValue(skill);
                }

                w.WriteEndArray();
                WriteList(w, "mounts", Mounts, s => Hex(s));
                WriteList(w, "doors", Doors, s => Hex(s));
                WriteList(w, "keys", Keys, s => Hex(s));
                w.WriteBoolean("fight", Fight);
                w.WriteBoolean("handOver", HandOver);

                if (Guard != null)
                {
                    w.WriteStartObject("guard");
                    w.WriteBoolean("talk", Guard.Talk);
                    w.WriteStartArray("loiter");
                    w.WriteNumberValue(Guard.LoiterRange);
                    w.WriteNumberValue(Guard.LoiterSeconds);
                    w.WriteEndArray();
                    w.WriteBoolean("attack", Guard.Attack);
                    w.WriteString("onAlarm", Guard.LogOut ? "logout" : "hide");
                    w.WriteNumber("hideAfter", Guard.HideAfter);
                    WriteList(w, "watchItems", Guard.WatchItems, s => Hex(s));
                    w.WriteStartArray("npcs");

                    foreach (uint serial in Guard.NpcSerials)
                    {
                        w.WriteStringValue(Hex(serial));
                    }

                    foreach (string name in Guard.NpcNames)
                    {
                        w.WriteStringValue(name);
                    }

                    w.WriteEndArray();
                    w.WriteStartArray("fidgets");

                    foreach (ushort action in Guard.Fidgets)
                    {
                        w.WriteNumberValue(action);
                    }

                    w.WriteEndArray();
                    w.WriteEndObject();
                }

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
                w.WriteStartArray("aim");
                w.WriteNumberValue(AimMin);
                w.WriteNumberValue(AimMax);
                w.WriteEndArray();
                w.WriteStartArray("repeat");
                w.WriteNumberValue(RepeatMin);
                w.WriteNumberValue(RepeatMax);
                w.WriteEndArray();
                w.WriteStartArray("repeatAim");
                w.WriteNumberValue(RepeatAimMin);
                w.WriteNumberValue(RepeatAimMax);
                w.WriteEndArray();
                w.WriteEndObject();
                w.WriteEndObject();
            }

            private static void WriteList<T>(Utf8JsonWriter w, string key, IEnumerable<T> values, Func<T, string> text)
            {
                w.WriteStartArray(key);

                foreach (T value in values)
                {
                    w.WriteStringValue(text(value));
                }

                w.WriteEndArray();
            }

            public static uint ParseNumber(string text)
            {
                if (text == null || !TryParseSerial(text, out uint value))
                {
                    throw new FormatException($"not a number: {text}");
                }

                return value;
            }
        }

        private sealed class Box
        {
            public string Name;
            public int X1, Y1, X2, Y2;
            public int ZMin = sbyte.MinValue, ZMax = sbyte.MaxValue;

            public bool Contains(int x, int y, int z) => x >= X1 && x <= X2 && y >= Y1 && y <= Y2 && z >= ZMin && z <= ZMax;

            public static Box Parse(string name, JsonElement box, JsonElement z)
            {
                if (box.GetArrayLength() != 4)
                {
                    throw new FormatException($"{name} needs four numbers: x1, y1, x2, y2");
                }

                var b = new Box
                {
                    Name = name,
                    X1 = Math.Min(box[0].GetInt32(), box[2].GetInt32()),
                    X2 = Math.Max(box[0].GetInt32(), box[2].GetInt32()),
                    Y1 = Math.Min(box[1].GetInt32(), box[3].GetInt32()),
                    Y2 = Math.Max(box[1].GetInt32(), box[3].GetInt32())
                };

                if (z.ValueKind == JsonValueKind.Array)
                {
                    b.ZMin = z[0].GetInt32();
                    b.ZMax = z[1].GetInt32();
                }

                return b;
            }

            public void Write(Utf8JsonWriter w)
            {
                w.WriteStartObject();
                w.WriteString("name", Name);
                w.WriteStartArray("box");
                w.WriteNumberValue(X1);
                w.WriteNumberValue(Y1);
                w.WriteNumberValue(X2);
                w.WriteNumberValue(Y2);
                w.WriteEndArray();
                w.WriteStartArray("z");
                w.WriteNumberValue(ZMin);
                w.WriteNumberValue(ZMax);
                w.WriteEndArray();
                w.WriteEndObject();
            }
        }

        // what the guard watches for; any of it logs the character out
        private sealed class GuardRules
        {
            public bool Talk = true;
            public int LoiterRange = 3, LoiterSeconds = 10;
            public bool Attack = true;
            public bool LogOut;     // "onAlarm": "logout" logs out instead of stopping for the agent to get away and hide
            public int HideAfter = 5; // seconds: if nobody starts getting the character away by then, the bridge hides him
            public readonly HashSet<uint> WatchItems = new HashSet<uint>(); // must stay in the backpack (runes)
            public readonly HashSet<uint> NpcSerials = new HashSet<uint>();  // townsfolk who talk and stand around
            public readonly HashSet<string> NpcNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            public readonly HashSet<ushort> Fidgets = new HashSet<ushort>(); // animations only NPCs do (idle fidgets)
        }

        // who set the guard off, and where they were last seen
        private sealed class Threat
        {
            public uint Serial;
            public string Name;
            public int X, Y;
            public DateTime Seen;
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
