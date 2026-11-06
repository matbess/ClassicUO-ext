// SPDX-License-Identifier: BSD-2-Clause

using ClassicUO.Game.Data;
using ClassicUO.Game.GameObjects;
using ClassicUO.Game.UI.Gumps;
using ClassicUO.Network;
using ClassicUO.Utility.Logging;
using System;
using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace ClassicUO.Game.Managers
{
    // Bridge 6 (2026-11-05, for Icepick's Blacksmithing and Clem's Cartography): the server's menus (the old picture
    // and text menus, 0x7C) and gumps (0xB0, 0xDD), the target cursor, skills, and an event log of what the server
    // shows and what the client sends, so a task the user does by hand can be recorded and then repeated.
    //   GET  /skills[?name=]          every skill: value, base, cap, lock, and the total
    //   GET  /gumps                   the menus and gumps open now, with their items, buttons and text
    //   GET  /events?after=           what happened: messages, menus and gumps shown, target cursors, skill changes,
    //                                 and what the client sent (double-clicks, menu choices, gump buttons, targets,
    //                                 picks and drops), whoever sent it, the user included
    //   POST /use?serial=             (no target) double-click a tool the rules allow, and say what the server showed
    //   POST /menu?serial=&id=&index= choose an item in a menu (index from 1; 0 cancels it)
    //   POST /gump?serial=&id=&button=[&switches=] press a gump button (0 closes it)
    //   POST /target?serial= | ?cancel=1  answer the server's target cursor with an item in reach
    // Only the packets listed in OnSent are ever read on the way out, and never their text entries: nothing the
    // client sends at login (the account name and password) goes near the log.
    internal sealed partial class AgentBridge
    {
        private const int EVENT_LOG = 1500;
        private const int ANSWER_TIMEOUT = 10000; // from a choice to the server's answer (crafting takes a few seconds)

        private static volatile AgentBridge _sending; // the running bridge, for NetClient.Send (on whichever thread)
        private readonly ConcurrentQueue<BridgeEvent> _sent = new ConcurrentQueue<BridgeEvent>();

        // only touched on the game thread
        private readonly Queue<BridgeEvent> _events = new Queue<BridgeEvent>();
        private long _lastEventId;
        private readonly List<Dialog> _dialogs = new List<Dialog>();
        private long _dialogCount; // every menu or gump the server shows
        private long _targetCount; // every target cursor the server asks for

        // ---- what the server shows (game thread) ----

        // 0x7C: a menu. Picture menus list items (graphic, hue, name); text menus ("gray") only names.
        private void OnMenuPacket(ReadOnlySpan<byte> data)
        {
            try
            {
                int i = 3;
                uint serial = BinaryPrimitives.ReadUInt32BigEndian(data.Slice(i));
                i += 4;
                ushort id = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(i));
                i += 2;
                int titleLength = data[i++];
                string title = Ascii(data.Slice(i, titleLength));
                i += titleLength;
                int count = data[i++];
                bool gray = count > 0 && BinaryPrimitives.ReadUInt16BigEndian(data.Slice(i)) == 0;
                var dialog = new Dialog { Kind = gray ? "text menu" : "menu", Serial = serial, Id = id, Title = title };

                for (int n = 1; n <= count; n++)
                {
                    ushort graphic = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(i));
                    ushort hue = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(i + 2));
                    i += 4;
                    int nameLength = data[i++];
                    dialog.Items.Add(new MenuItem { Index = n, Graphic = graphic, Hue = hue, Name = Ascii(data.Slice(i, nameLength)) });
                    i += nameLength;
                }

                AddDialog(dialog);
            }
            catch (Exception ex)
            {
                // never let a strange packet break the client's own handling of it
                AddEvent("menu", ("error", $"could not read the menu packet: {ex.Message}"));
            }
        }

        // called by PacketHandlers.CreateGump for every gump the server sends (0xB0 and the compressed 0xDD)
        public void OnServerGump(uint sender, uint gumpId, string layout, string[] lines)
        {
            if (_listener == null)
            {
                return;
            }

            try
            {
                AddDialog(new Dialog { Kind = "gump", Serial = sender, Id = gumpId, Layout = layout ?? "", Lines = lines ?? Array.Empty<string>() });
            }
            catch (Exception ex)
            {
                Log.Warn($"Agent bridge: gump {gumpId:X8}: {ex.Message}");
            }
        }

        private void AddDialog(Dialog dialog)
        {
            dialog.Number = ++_dialogCount;
            dialog.Time = DateTime.Now;
            _dialogs.RemoveAll(d => d.Serial == dialog.Serial && d.Id == dialog.Id && d.Kind == dialog.Kind);
            _dialogs.Add(dialog);

            while (_dialogs.Count > 20)
            {
                _dialogs.RemoveAt(0);
            }

            var e = new BridgeEvent { Kind = dialog.Kind, Dialog = dialog };
            AddEvent(e);
        }

        // 0x6C from the server: it wants a target
        private void OnTargetPacket(ReadOnlySpan<byte> data)
        {
            if (data.Length < 7)
            {
                return;
            }

            _targetCount++;

            try
            {
                AddEvent("target cursor", ("cursor", Hex(BinaryPrimitives.ReadUInt32BigEndian(data.Slice(2)))), ("on", data[1] == 1 ? "ground" : "object"));
            }
            catch (Exception ex)
            {
                Log.Warn($"Agent bridge: target cursor: {ex.Message}");
            }
        }

        // 0x3A: one skill changed (0xFF, or 0xDF with its cap); the full lists at login aren't logged
        private void OnSkillPacket(ReadOnlySpan<byte> data)
        {
            if (data.Length < 11 || data[3] != 0xFF && data[3] != 0xDF)
            {
                return;
            }

            try
            {
                int id = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(4));
                Skill[] skills = _world.Player?.Skills;
                string name = skills != null && id < skills.Length ? skills[id].Name : $"skill {id}";

                AddEvent
                (
                    "skill",
                    ("skill", id),
                    ("name", name),
                    ("value", BinaryPrimitives.ReadUInt16BigEndian(data.Slice(6)) / 10.0),
                    ("base", BinaryPrimitives.ReadUInt16BigEndian(data.Slice(8)) / 10.0)
                );
            }
            catch (Exception ex)
            {
                Log.Warn($"Agent bridge: skill update: {ex.Message}");
            }
        }

        // ---- what the client sends (any thread) ----

        // called by NetClient.Send before the packet is encrypted. Reads only these packets, and copies out only
        // their numbers.
        public static void OnSent(ReadOnlySpan<byte> data)
        {
            AgentBridge bridge = _sending;

            if (bridge == null || data.Length < 5)
            {
                return;
            }

            BridgeEvent e = null;

            // never let the log get in the way of sending
            try
            {
                e = ReadSent(data);
            }
            catch (Exception)
            {
            }

            if (e != null)
            {
                bridge._sent.Enqueue(e);
            }
        }

        private static BridgeEvent ReadSent(ReadOnlySpan<byte> d)
        {
            switch (d[0])
            {
                case 0x06:
                    return Sent("sent double-click", ("serial", Hex(U32(d, 1) & 0x7FFFFFFF)));

                case 0x09:
                    return Sent("sent single-click", ("serial", Hex(U32(d, 1))));

                case 0x07 when d.Length >= 7:
                    return Sent("sent pick up", ("serial", Hex(U32(d, 1))), ("amount", (int)U16(d, 5)));

                case 0x08 when d.Length >= 14:
                    return Sent("sent drop", ("serial", Hex(U32(d, 1))), ("x", (int)U16(d, 5)), ("y", (int)U16(d, 7)), ("container", Hex(U32(d, d.Length - 4))));

                case 0x13 when d.Length >= 10:
                    return Sent("sent equip", ("serial", Hex(U32(d, 1))), ("layer", (int)d[5]), ("on", Hex(U32(d, 6))));

                case 0x12 when d.Length >= 4:
                    // a skill ("21 0"), a spell or a door: numbers and a few words, never typed text
                    return Sent("sent use", ("type", Hex((ushort)d[3])), ("what", Ascii(d.Slice(4)).TrimEnd('\0')));

                case 0x6C when d.Length >= 19:
                    return Sent
                    (
                        "sent target",
                        ("on", d[1] == 1 ? "ground" : "object"),
                        ("cursor", Hex(U32(d, 2))),
                        ("serial", Hex(U32(d, 7))),
                        ("x", (int)U16(d, 11)),
                        ("y", (int)U16(d, 13)),
                        ("z", (int)(sbyte)d[16]),
                        ("graphic", Hex(U16(d, 17)))
                    );

                case 0x7D when d.Length >= 9:
                    return Sent
                    (
                        "sent menu choice",
                        ("serial", Hex(U32(d, 1))),
                        ("menu", Hex(U16(d, 5))),
                        ("index", d.Length >= 9 ? (int)U16(d, 7) : 0),
                        ("graphic", d.Length >= 11 ? Hex(U16(d, 9)) : null)
                    );

                case 0xB1 when d.Length >= 19:
                {
                    int switchCount = (int)Math.Min(U32(d, 15), 64);
                    var switches = new List<string>();

                    for (int n = 0; n < switchCount && 19 + n * 4 + 4 <= d.Length; n++)
                    {
                        switches.Add(U32(d, 19 + n * 4).ToString(CultureInfo.InvariantCulture));
                    }

                    // the text typed into entries is never read
                    return Sent
                    (
                        "sent gump button",
                        ("serial", Hex(U32(d, 3))),
                        ("gump", Hex(U32(d, 7))),
                        ("button", (long)U32(d, 11)),
                        ("switches", string.Join(",", switches))
                    );
                }

                case 0x3A when d.Length >= 6:
                    return Sent("sent skill lock", ("id", (int)U16(d, 3)), ("lock", (int)d[5]));

                case 0x3B when d.Length >= 8:
                    return Sent("sent buy", ("vendor", Hex(U32(d, 3))), ("items", (d.Length - 8) / 7));

                case 0x9F when d.Length >= 9:
                    return Sent("sent sell", ("vendor", Hex(U32(d, 3))), ("items", (int)U16(d, 7)));
            }

            return null;
        }

        private static uint U32(ReadOnlySpan<byte> d, int at) => BinaryPrimitives.ReadUInt32BigEndian(d.Slice(at));

        private static ushort U16(ReadOnlySpan<byte> d, int at) => BinaryPrimitives.ReadUInt16BigEndian(d.Slice(at));

        private static BridgeEvent Sent(string kind, params (string, object)[] fields) => new BridgeEvent { Kind = kind, Fields = fields, Time = DateTime.Now };

        // game thread: moves what the client sent into the log, names what it can, and forgets answered dialogs
        private void TakeSent()
        {
            while (_sent.TryDequeue(out BridgeEvent e))
            {
                if (e.Kind == "sent menu choice" || e.Kind == "sent gump button")
                {
                    string serial = Field(e, "serial");
                    string id = Field(e, e.Kind == "sent menu choice" ? "menu" : "gump");
                    _dialogs.RemoveAll(d => Hex(d.Serial) == serial && (d.Kind == "gump" ? Hex(d.Id) : Hex((ushort)d.Id)) == id);
                }

                if (Field(e, "serial") is string s && TryParseSerial(s, out uint serial2) && _world.Items.Get(serial2) is Item item)
                {
                    e.Name = item.Name ?? item.ItemData.Name;
                }

                AddEvent(e);
            }
        }

        private static string Field(BridgeEvent e, string key)
        {
            foreach ((string k, object v) in e.Fields)
            {
                if (k == key)
                {
                    return v as string;
                }
            }

            return null;
        }

        private void AddEvent(string kind, params (string, object)[] fields) => AddEvent(new BridgeEvent { Kind = kind, Fields = fields });

        private void AddEvent(BridgeEvent e)
        {
            e.Id = ++_lastEventId;

            if (e.Time == default)
            {
                e.Time = DateTime.Now;
            }

            _events.Enqueue(e);

            while (_events.Count > EVENT_LOG)
            {
                _events.Dequeue();
            }
        }

        private void ClearDialogs()
        {
            _dialogs.Clear();
            _events.Clear();
            _sent.Clear();
        }

        // ---- requests (listener thread) ----

        private byte[] HandleDialogs(string method, string path, Dictionary<string, string> query)
        {
            switch (path)
            {
                case "/skills":
                    RequireMethod(method, "GET");
                    string only = query.TryGetValue("name", out string n) ? n : null;

                    return OnGame(() => Json(w => WriteSkills(w, only)));

                case "/gumps":
                    RequireMethod(method, "GET");

                    return OnGame(() => Json(w => { w.WriteStartObject(); WriteOpenDialogs(w, 0); w.WriteEndObject(); }));

                case "/events":
                    RequireMethod(method, "GET");
                    long after = GetLong(query, "after", 0);

                    return OnGame(() => Json(w => WriteEvents(w, after)));

                case "/menu":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return AnswerMenu(GetSerial(query), GetSerial(query, "id"), GetRequiredInt(query, "index"));

                case "/gump":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return AnswerGump(GetSerial(query), GetSerial(query, "id"), GetRequiredInt(query, "button"), query.TryGetValue("switches", out string sw) ? sw : "");

                case "/target":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return AnswerTarget(GetInt(query, "cancel", 0) != 0 ? 0 : GetSerial(query));
            }

            return null;
        }

        // double-clicks a tool the rules allow (a smith's hammer) and waits for what the server shows: a menu, a gump,
        // a target cursor or a message
        private byte[] UseTool(uint serial)
        {
            Rules rules = RequireRules();

            if (rules.Doors.Contains(serial))
            {
                return UseDoor(serial, rules);
            }

            long before = 0, dialogs = 0, targets = 0;

            for (int attempt = 0; attempt < 2; attempt++)
            {
                WaitForActionSlot();

                (before, dialogs, targets) = OnGame
                (
                    () =>
                    {
                        TakeSent();
                        CheckNobodyElse(rules);
                        Item item = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such item nearby");
                        CheckUsable(item, rules);

                        if (_world.TargetManager.IsTargeting)
                        {
                            _world.TargetManager.CancelTarget();
                        }

                        LogAction("use (double-click)", serial);
                        GameActions.DoubleClick(_world, serial);

                        return (_lastMessageId, _dialogCount, _targetCount);
                    }
                );

                long b = before, dc = dialogs, tc = targets;
                WaitFor(() => _dialogCount > dc || _targetCount > tc || HasAnswerAfter(b), TARGET_TIMEOUT);

                bool shown = OnGame(() => _dialogCount > dc || _targetCount > tc);

                if (shown || !OnGame(() => SawMessage(b, MUST_WAIT)))
                {
                    break;
                }
            }

            long b2 = before, dc2 = dialogs, tc2 = targets;

            if (!OnGame(() => _dialogCount > dc2 || _targetCount > tc2 || HasMessageAfter(b2)))
            {
                Halt($"no answer when using {Hex(serial)}");
            }

            Thread.Sleep(SETTLE_TIME);

            return OnGame(() => Json(w => WriteAnswer(w, before, dialogs)));
        }

        private byte[] AnswerMenu(uint serial, uint id, int index)
        {
            Rules rules = RequireRules();
            WaitForReply(rules);

            (long before, long dialogs, long targets) = OnGame
            (
                () =>
                {
                    TakeSent();
                    CheckNobodyElse(rules);
                    Dialog d = FindOpen(serial, id, false) ?? throw new BridgeException(404, "no such menu is open");

                    if (index < 0 || index > d.Items.Count)
                    {
                        throw new BridgeException(400, $"the menu has {d.Items.Count} items (index from 1, 0 cancels)");
                    }

                    LogAction($"menu {Hex((ushort)id)} item {index}", serial);

                    if (d.Kind == "menu")
                    {
                        MenuItem item = index > 0 ? d.Items[index - 1] : null;
                        NetClient.Socket.Send_MenuResponse(serial, (ushort)id, index, item?.Graphic ?? 0, item?.Hue ?? 0);
                    }
                    else
                    {
                        NetClient.Socket.Send_GrayMenuResponse(serial, (ushort)id, (ushort)index);
                    }

                    CloseClientGump(d);

                    return (_lastMessageId, _dialogCount, _targetCount);
                }
            );

            return AfterAnswer(index != 0, before, dialogs, targets, $"choosing item {index} in menu {Hex((ushort)id)}");
        }

        private byte[] AnswerGump(uint serial, uint id, int button, string switchText)
        {
            Rules rules = RequireRules();
            var switches = new List<uint>();

            foreach (string part in switchText.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                switches.Add(uint.TryParse(part, NumberStyles.Integer, CultureInfo.InvariantCulture, out uint s) ? s : throw new BridgeException(400, $"not a switch number: {part}"));
            }

            WaitForReply(rules);

            (long before, long dialogs, long targets) = OnGame
            (
                () =>
                {
                    TakeSent();
                    CheckNobodyElse(rules);
                    Dialog d = FindOpen(serial, id, true) ?? throw new BridgeException(404, "no such gump is open");

                    if (button != 0 && !d.ReplyButtons().Contains(button))
                    {
                        throw new BridgeException(400, $"the gump has no button {button}");
                    }

                    LogAction($"gump {Hex(id)} button {button}", serial);
                    GameActions.ReplyGump(serial, id, button, switches.ToArray(), Array.Empty<Tuple<ushort, string>>());
                    CloseClientGump(d);

                    return (_lastMessageId, _dialogCount, _targetCount);
                }
            );

            return AfterAnswer(button != 0, before, dialogs, targets, $"pressing button {button} in gump {Hex(id)}");
        }

        // answers the server's target cursor with an item (in reach, inside the rules), or cancels it (serial 0)
        private byte[] AnswerTarget(uint serial)
        {
            Rules rules = RequireRules();
            WaitForReply(rules);

            (long before, long dialogs, long targets) = OnGame
            (
                () =>
                {
                    TakeSent();

                    if (!_world.TargetManager.IsTargeting)
                    {
                        throw new BridgeException(409, "no target cursor is up");
                    }

                    if (serial == 0)
                    {
                        LogAction("cancel target", 0);
                        _world.TargetManager.CancelTarget();

                        return (_lastMessageId, _dialogCount, _targetCount);
                    }

                    CheckNobodyElse(rules);

                    if (SerialHelper.IsMobile(serial))
                    {
                        CheckFightTarget(serial, rules);
                    }
                    else
                    {
                        Item aim = _world.Items.Get(serial) ?? throw new BridgeException(404, "no such item nearby");

                        // a door the rules name lies outside the areas (on the house's edge): only reach matters
                        CheckInReach(rules.Doors.Contains(serial) ? aim : CheckReachable(aim, rules, "target"), REACH);
                    }

                    LogAction("target", serial);
                    _world.TargetManager.Target(serial);

                    return (_lastMessageId, _dialogCount, _targetCount);
                }
            );

            // in a fight the answer is waited for briefly and never halts the bridge
            bool fight = SerialHelper.IsMobile(serial);

            return AfterAnswer(serial != 0, before, dialogs, targets, $"targeting {Hex(serial)}", fight ? FIGHT_ANSWER : ANSWER_TIMEOUT, !fight);
        }

        // waits for the server's answer to a choice: another menu or gump, a target cursor or a message
        private byte[] AfterAnswer(bool expectAnswer, long before, long dialogs, long targets, string what, int timeout = ANSWER_TIMEOUT, bool haltIfNone = true)
        {
            if (expectAnswer)
            {
                if (!WaitFor(() => _dialogCount > dialogs || _targetCount > targets || HasAnswerAfter(before), timeout) && haltIfNone)
                {
                    Halt($"no answer after {what}");
                }

                Thread.Sleep(SETTLE_TIME);
            }

            // the next action waits a full gap from the answer
            PaceFromNow();

            return OnGame(() => Json(w => WriteAnswer(w, before, dialogs)));
        }

        // the server's own messages, or the character's (some results come as the character's emote)
        private bool HasAnswerAfter(long after)
        {
            uint player = _world.Player?.Serial ?? 0;

            foreach (Message m in _messages)
            {
                if (m.Id > after && (m.Serial == 0 || m.Serial == player))
                {
                    return true;
                }
            }

            return false;
        }

        // a person answers a menu or a cursor as quickly as they'd aim: the rules' "aim", or about half a second
        private void WaitForReply(Rules rules)
        {
            CheckNotHalted();

            while (OnGame(IsSaving))
            {
                Thread.Sleep(500);
            }

            if (rules.AimGiven)
            {
                Aim(rules);
            }
            else
            {
                Thread.Sleep(_random.Next(500, 1000));
            }
        }

        // game thread
        private Dialog FindOpen(uint serial, uint id, bool gump)
        {
            PruneDialogs();

            for (int i = _dialogs.Count - 1; i >= 0; i--)
            {
                Dialog d = _dialogs[i];

                if (d.Serial == serial && (gump ? d.Kind == "gump" && d.Id == id : d.Kind != "gump" && (ushort)d.Id == (ushort)id))
                {
                    return d;
                }
            }

            return null;
        }

        // game thread: drops dialogs the client no longer shows (answered, closed by hand, or closed by the server)
        private void PruneDialogs()
        {
            TakeSent();
            _dialogs.RemoveAll(d => ClientGump(d) == null && (DateTime.Now - d.Time).TotalSeconds > 2);
        }

        private static Gump ClientGump(Dialog d)
        {
            for (LinkedListNode<Gump> node = UIManager.Gumps.Last; node != null; node = node.Previous)
            {
                Gump g = node.Value;

                if (g == null || g.IsDisposed || g.LocalSerial != d.Serial)
                {
                    continue;
                }

                if (d.Kind == "gump" ? g.IsFromServer && g.ServerSerial == d.Id : (g is MenuGump || g is GrayMenuGump) && (ushort)g.ServerSerial == (ushort)d.Id)
                {
                    return g;
                }
            }

            return null;
        }

        private void CloseClientGump(Dialog d)
        {
            ClientGump(d)?.Dispose();
            _dialogs.Remove(d);
        }

        // ---- writing (game thread) ----

        private void WriteAnswer(Utf8JsonWriter w, long before, long dialogs)
        {
            PruneDialogs();
            w.WriteStartObject();
            w.WriteBoolean("targeting", _world.TargetManager.IsTargeting);
            WriteOpenDialogs(w, dialogs);
            WriteMessagesSince(w, before, 0);
            w.WriteNumber("weight", _world.Player.Weight);
            w.WriteNumber("weightMax", _world.Player.WeightMax);
            w.WriteEndObject();
        }

        // the dialogs open now that the server showed after the given count
        private void WriteOpenDialogs(Utf8JsonWriter w, long after)
        {
            PruneDialogs();
            w.WriteStartArray("dialogs");

            foreach (Dialog d in _dialogs)
            {
                if (d.Number > after && (ClientGump(d) != null || (DateTime.Now - d.Time).TotalSeconds <= 2))
                {
                    WriteDialog(w, d);
                }
            }

            w.WriteEndArray();
        }

        private static void WriteDialog(Utf8JsonWriter w, Dialog d)
        {
            w.WriteStartObject();
            w.WriteString("kind", d.Kind);
            w.WriteString("serial", Hex(d.Serial));
            w.WriteString("id", d.Kind == "gump" ? Hex(d.Id) : Hex((ushort)d.Id));
            w.WriteNumber("number", d.Number);
            w.WriteString("time", d.Time.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture));

            if (d.Kind != "gump")
            {
                w.WriteString("title", d.Title);
                w.WriteStartArray("items");

                foreach (MenuItem item in d.Items)
                {
                    w.WriteStartObject();
                    w.WriteNumber("index", item.Index);
                    w.WriteString("name", item.Name);

                    if (d.Kind == "menu")
                    {
                        w.WriteString("graphic", Hex(item.Graphic));
                        w.WriteNumber("hue", item.Hue);
                    }

                    w.WriteEndObject();
                }

                w.WriteEndArray();
            }
            else
            {
                List<GumpElement> elements = d.Elements();
                w.WriteStartArray("buttons");

                foreach (GumpElement b in elements)
                {
                    if (b.Button > 0 && b.ButtonType == 1)
                    {
                        w.WriteStartObject();
                        w.WriteNumber("button", b.Button);
                        w.WriteNumber("x", b.X);
                        w.WriteNumber("y", b.Y);
                        w.WriteString("label", d.LabelFor(b, elements));
                        w.WriteEndObject();
                    }
                }

                w.WriteEndArray();
                w.WriteStartArray("texts");

                foreach (GumpElement t in elements)
                {
                    if (t.Text != null)
                    {
                        w.WriteStartObject();
                        w.WriteNumber("x", t.X);
                        w.WriteNumber("y", t.Y);
                        w.WriteNumber("page", t.Page);
                        w.WriteString("text", t.Text);
                        w.WriteEndObject();
                    }
                }

                w.WriteEndArray();
                w.WriteStartArray("switches");

                foreach (GumpElement s in elements)
                {
                    if (s.Switch > 0)
                    {
                        w.WriteStartObject();
                        w.WriteNumber("switch", s.Switch);
                        w.WriteNumber("x", s.X);
                        w.WriteNumber("y", s.Y);
                        w.WriteBoolean("on", s.On);
                        w.WriteString("label", d.LabelFor(s, elements));
                        w.WriteEndObject();
                    }
                }

                w.WriteEndArray();
                w.WriteString("layout", d.Layout);
                w.WriteStartArray("lines");

                foreach (string line in d.Lines)
                {
                    w.WriteStringValue(line);
                }

                w.WriteEndArray();
            }

            w.WriteEndObject();
        }

        private void WriteEvents(Utf8JsonWriter w, long after)
        {
            TakeSent();
            w.WriteStartObject();
            w.WriteNumber("lastEventId", _lastEventId);
            w.WriteStartArray("events");

            foreach (BridgeEvent e in _events)
            {
                if (e.Id <= after)
                {
                    continue;
                }

                w.WriteStartObject();
                w.WriteNumber("id", e.Id);
                w.WriteString("time", e.Time.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture));
                w.WriteString("kind", e.Kind);

                if (e.Name != null)
                {
                    w.WriteString("name", e.Name);
                }

                foreach ((string key, object value) in e.Fields)
                {
                    switch (value)
                    {
                        case null:
                            break;

                        case string s:
                            w.WriteString(key, s);

                            break;

                        case int i:
                            w.WriteNumber(key, i);

                            break;

                        case long l:
                            w.WriteNumber(key, l);

                            break;

                        case double f:
                            w.WriteNumber(key, f);

                            break;

                        default:
                            w.WriteString(key, Convert.ToString(value, CultureInfo.InvariantCulture));

                            break;
                    }
                }

                if (e.Dialog != null)
                {
                    w.WritePropertyName("dialog");
                    WriteDialog(w, e.Dialog);
                }

                w.WriteEndObject();
            }

            w.WriteEndArray();
            w.WriteEndObject();
        }

        private void WriteSkills(Utf8JsonWriter w, string only)
        {
            Skill[] skills = _world.Player.Skills;
            double total = 0;
            w.WriteStartObject();
            w.WriteStartArray("skills");

            foreach (Skill s in skills)
            {
                total += s.Base;

                if (only != null && !s.Name.Contains(only, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                w.WriteStartObject();
                w.WriteNumber("id", s.Index);
                w.WriteString("name", s.Name);
                w.WriteNumber("value", s.Value);
                w.WriteNumber("base", s.Base);
                w.WriteNumber("cap", s.Cap);
                w.WriteString("lock", s.Lock.ToString().ToLowerInvariant());
                w.WriteEndObject();
            }

            w.WriteEndArray();
            w.WriteNumber("total", Math.Round(total, 1));
            w.WriteEndObject();
        }

        private static string Ascii(ReadOnlySpan<byte> bytes) => Encoding.ASCII.GetString(bytes);

        // ---- types ----

        private sealed class BridgeEvent
        {
            public long Id;
            public DateTime Time;
            public string Kind;
            public string Name; // the item a sent action was about, when the client knows it
            public (string, object)[] Fields = Array.Empty<(string, object)>();
            public Dialog Dialog;
        }

        private sealed class MenuItem
        {
            public int Index;
            public ushort Graphic, Hue;
            public string Name;
        }

        private sealed class GumpElement
        {
            public string Command;
            public int X, Y, Page;
            public int Button, ButtonType; // reply buttons have type 1
            public int Switch;
            public bool On;
            public string Text;
        }

        private sealed class Dialog
        {
            public string Kind; // "menu" (picture menu), "text menu", "gump"
            public uint Serial, Id;
            public long Number;
            public DateTime Time;
            public string Title;
            public readonly List<MenuItem> Items = new List<MenuItem>();
            public string Layout;
            public string[] Lines;
            private List<GumpElement> _elements;

            public HashSet<int> ReplyButtons()
            {
                var set = new HashSet<int>();

                foreach (GumpElement e in Elements())
                {
                    if (e.Button > 0 && e.ButtonType == 1)
                    {
                        set.Add(e.Button);
                    }
                }

                return set;
            }

            // the layout's commands, "{ button 10 20 4005 4007 1 0 3 }" and so on, with their text worked out
            public List<GumpElement> Elements()
            {
                if (_elements != null)
                {
                    return _elements;
                }

                _elements = new List<GumpElement>();
                int page = 0;
                int at = 0;
                string layout = Layout ?? "";

                while ((at = layout.IndexOf('{', at)) >= 0)
                {
                    int end = layout.IndexOf('}', at);

                    if (end < 0)
                    {
                        break;
                    }

                    string[] t = Tokens(layout.Substring(at + 1, end - at - 1));
                    at = end + 1;

                    if (t.Length == 0)
                    {
                        continue;
                    }

                    string cmd = t[0].ToLowerInvariant();
                    int N(int i) => i < t.Length && int.TryParse(t[i], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) ? v : 0;
                    var e = new GumpElement { Command = cmd, X = N(1), Y = N(2), Page = page };

                    switch (cmd)
                    {
                        case "page":
                            page = N(1);

                            continue;

                        case "button":
                            e.ButtonType = N(5);
                            e.Button = N(7);

                            break;

                        case "buttontileart":
                            e.ButtonType = N(5);
                            e.Button = N(7);

                            break;

                        case "checkbox":
                        case "radio":
                            e.On = N(5) != 0;
                            e.Switch = N(6);

                            break;

                        case "text":
                            e.Text = Line(N(4));

                            break;

                        case "croppedtext":
                            e.Text = Line(N(6));

                            break;

                        case "htmlgump":
                            e.Text = Line(N(5));

                            break;

                        case "xmfhtmlgump":
                        case "xmfhtmlgumpcolor":
                            e.Text = Cliloc(N(5), null);

                            break;

                        case "xmfhtmltok":
                            e.Text = Cliloc(N(8), t.Length > 9 ? t[9].Trim('@') : null);

                            break;

                        case "tooltip":
                            e.Text = null;

                            break;

                        default:
                            continue;
                    }

                    _elements.Add(e);
                }

                return _elements;
            }

            // the text next to a button or switch: the nearest one on the same row, to its right
            public string LabelFor(GumpElement control, List<GumpElement> elements)
            {
                GumpElement best = null;

                foreach (GumpElement t in elements)
                {
                    if (t.Text == null || t.Page != control.Page && t.Page != 0 || Math.Abs(t.Y - control.Y) > 8 || t.X < control.X || t.X - control.X > 400)
                    {
                        continue;
                    }

                    if (best == null || t.X - control.X < best.X - control.X)
                    {
                        best = t;
                    }
                }

                return best?.Text;
            }

            private string Line(int i) => Lines != null && i >= 0 && i < Lines.Length ? Lines[i] : null;

            private static string Cliloc(int number, string args)
            {
                string text = Client.Game.UO.FileManager.Clilocs.GetString(number, $"#{number}");

                if (!string.IsNullOrEmpty(args))
                {
                    string[] parts = args.Split('\t');

                    for (int i = 0; i < parts.Length; i++)
                    {
                        int start = text.IndexOf('~');
                        int stop = start >= 0 ? text.IndexOf('~', start + 1) : -1;

                        if (stop < 0)
                        {
                            break;
                        }

                        string value = parts[i].StartsWith('#') && int.TryParse(parts[i].AsSpan(1), out int c) ? Client.Game.UO.FileManager.Clilocs.GetString(c, parts[i]) : parts[i];
                        text = text.Substring(0, start) + value + text.Substring(stop + 1);
                    }
                }

                return text;
            }

            // splits on spaces, keeping "@a b@" together
            private static string[] Tokens(string s)
            {
                var list = new List<string>();
                int i = 0;

                while (i < s.Length)
                {
                    while (i < s.Length && char.IsWhiteSpace(s[i]))
                    {
                        i++;
                    }

                    if (i >= s.Length)
                    {
                        break;
                    }

                    int start = i;

                    if (s[i] == '@')
                    {
                        int close = s.IndexOf('@', i + 1);
                        i = close < 0 ? s.Length : close + 1;
                    }
                    else
                    {
                        while (i < s.Length && !char.IsWhiteSpace(s[i]))
                        {
                            i++;
                        }
                    }

                    list.Add(s.Substring(start, i - start));
                }

                return list.ToArray();
            }
        }
    }
}
