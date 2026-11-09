// SPDX-License-Identifier: BSD-2-Clause

using ClassicUO.Game.Data;
using ClassicUO.Game.GameObjects;
using ClassicUO.Game.UI.Gumps;
using ClassicUO.Network;
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace ClassicUO.Game.Managers
{
    // Bridge 12 (2026-11-08, Clem's trips to the mapmaker in Ocllo; CARTO.md): buying from and selling to a vendor.
    // Only a vendor whose single-click name carries one of the rules' "vendors" titles ("Cador the mapmaker": the user,
    // 2026-11-08, there are several NPCs in the shop), only the rules' "goods" (graphics), and never more gold at once
    // than the rules' "spend".
    //   POST /shop?vendor=&mode=buy|sell    say "<his name> buy" (or sell) next to him and wait for his window; he must
    //                                       have been single-clicked (/name) so his title is known
    //   GET  /shop                          the vendor window open now: buy or sell, every item, its price and amount
    //   POST /shop?close=1                  close it without dealing
    //   POST /buy?items=SERIAL:AMOUNT,...   buy from the open buy window; waits for the goods to land in the pack
    //   POST /sell?items=SERIAL:AMOUNT,...  sell from the open sell window; waits for them to leave the pack
    //   POST /paperdoll?serial=A,B,...      ask for people's paperdolls and read their titles, closing the paperdolls
    //                                       again: an NPC's is "Cador the mapmaker" (a single click shows only "Cador"
    //                                       here), a player's "Bob" or "The Glorious Lord Bob, Grandmaster Mage"
    // The event log notes every buy and sell list the server sends ("shop list"), so a visit by hand shows them.
    internal sealed partial class AgentBridge
    {
        private const int SHOP_RANGE = 3;           // a vendor answers "<name> buy" from this close
        private const int SHOP_TIMEOUT = 4000;      // from the words to his window
        private const int SHOP_DEAL_TIMEOUT = 8000; // from the deal to the goods landing (a hundred maps come one by one)
        private const int SHOP_QUIET = 1000;        // the goods have stopped coming once nothing changed for this long
        private const ushort GOLD = 0x0EED;

        // game thread: the last sell list (0x9E), which otherwise only the shop gump keeps, and a count of the lists
        private uint _sellVendor;
        private readonly List<ShopEntry> _sellList = new List<ShopEntry>();
        private long _buyLists;
        private long _sellLists;
        private readonly Dictionary<uint, long> _paperdolls = new Dictionary<uint, long>(); // game thread: serial -> when its paperdoll came (packet count)
        private long _paperdollCount;
        private const int PAPERDOLL_TIMEOUT = 2000;
        private const int PAPERDOLL_RANGE = 18;

        // ---- what the server shows (game thread, before the client's own handler) ----

        // 0x88: a paperdoll (the client keeps its text as the mobile's Title)
        private void OnPaperdollPacket(ReadOnlySpan<byte> data)
        {
            if (data.Length >= 5)
            {
                _paperdolls[BinaryPrimitives.ReadUInt32BigEndian(data.Slice(1))] = ++_paperdollCount;
            }
        }

        private void OnShopPacket(ReadOnlySpan<byte> data)
        {
            if (data[0] == 0x74 && data.Length >= 8)
            {
                _buyLists++;
                uint container = BinaryPrimitives.ReadUInt32BigEndian(data.Slice(3));
                Item box = _world.Items.Get(container);
                AddEvent("shop list", ("mode", "buy"), ("vendor", box != null ? Hex(box.Container) : null), ("items", (int)data[7]));

                return;
            }

            if (data[0] != 0x9E || data.Length < 9)
            {
                return;
            }

            uint vendor = BinaryPrimitives.ReadUInt32BigEndian(data.Slice(3));
            int count = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(7));
            var entries = new List<ShopEntry>();
            int at = 9;

            for (int i = 0; i < count && at + 14 <= data.Length; i++)
            {
                var entry = new ShopEntry
                {
                    Serial = BinaryPrimitives.ReadUInt32BigEndian(data.Slice(at)),
                    Graphic = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(at + 4)),
                    Hue = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(at + 6)),
                    Amount = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(at + 8)),
                    Price = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(at + 10))
                };

                int nameLength = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(at + 12));
                at += 14;

                if (at + nameLength > data.Length)
                {
                    break;
                }

                string name = Encoding.ASCII.GetString(data.Slice(at, nameLength)).TrimEnd('\0');
                at += nameLength;

                if (int.TryParse(name, out int cliloc))
                {
                    name = Client.Game.UO.FileManager.Clilocs.GetString(cliloc) ?? name;
                }
                else if (string.IsNullOrEmpty(name))
                {
                    name = Client.Game.UO.FileManager.TileData.StaticData[entry.Graphic].Name;
                }

                entry.Name = name;
                entries.Add(entry);
            }

            _sellVendor = vendor;
            _sellList.Clear();
            _sellList.AddRange(entries);
            _sellLists++;
            AddEvent("shop list", ("mode", "sell"), ("vendor", Hex(vendor)), ("items", entries.Count));
        }

        // ---- requests (listener thread) ----

        private byte[] HandleShop(string method, string path, Dictionary<string, string> query)
        {
            switch (path)
            {
                case "/shop" when method == "GET":
                    return OnGame(() => Json(WriteShop));

                case "/shop":
                    RequireMethod(method, "POST");

                    if (GetInt(query, "close", 0) != 0)
                    {
                        return OnGame(() => Json(w => WriteDone(w, CloseShop())));
                    }

                    CheckNotHalted();
                    CheckNoAlarm();

                    return OpenShop(GetSerial(query, "vendor"), query.TryGetValue("mode", out string mode) ? mode : "");

                case "/buy":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return Deal(true, GetDeal(query));

                case "/sell":
                    RequireMethod(method, "POST");
                    CheckNotHalted();
                    CheckNoAlarm();

                    return Deal(false, GetDeal(query));

                case "/paperdoll":
                    RequireMethod(method, "POST");
                    CheckNotHalted();

                    return Paperdolls(GetSerials(query));
            }

            return null;
        }

        private static List<(uint Serial, int Amount)> GetDeal(Dictionary<string, string> query)
        {
            var deal = new List<(uint, int)>();

            if (!query.TryGetValue("items", out string text) || string.IsNullOrWhiteSpace(text))
            {
                throw new BridgeException(400, "give items=SERIAL:AMOUNT,...");
            }

            foreach (string part in text.Split(',', StringSplitOptions.RemoveEmptyEntries))
            {
                string[] pair = part.Split(':');

                if (pair.Length != 2 || !TryParseSerial(pair[0], out uint serial) ||
                    !int.TryParse(pair[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int amount) || amount < 1)
                {
                    throw new BridgeException(400, $"not SERIAL:AMOUNT: {part}");
                }

                deal.Add((serial, amount));
            }

            return deal;
        }

        // the vendor's own name and the title the rules allow, from his paperdoll ("Cador the mapmaker") or his
        // single-click name where that carries the title
        private (string Name, string Title) VendorName(Mobile vendor, Rules rules)
        {
            string text = !string.IsNullOrEmpty(vendor.Title) ? vendor.Title.Trim('\0', ' ') : null;

            if (string.IsNullOrEmpty(text) && _labels.TryGetValue(vendor.Serial, out Label label) && label.Lines.Count > 0)
            {
                text = string.Join(" ", label.Lines);
            }

            if (string.IsNullOrEmpty(text))
            {
                throw new BridgeException(409, $"ask for {Hex(vendor.Serial)}'s paperdoll first (/paperdoll), so his title is known");
            }

            foreach (string title in rules.Vendors)
            {
                int at = text.IndexOf(" the " + title, StringComparison.OrdinalIgnoreCase);

                if (at > 0)
                {
                    string name = text.Substring(0, at).Trim();

                    return (name.Length > 0 ? name : vendor.Name, title);
                }
            }

            throw new BridgeException(403, $"\"{text}\" is not a vendor the rules allow ({string.Join(", ", rules.Vendors)})");
        }

        private byte[] OpenShop(uint vendorSerial, string mode)
        {
            Rules rules = RequireRules();

            if (rules.Vendors.Count == 0)
            {
                throw new BridgeException(403, "the rules name no vendors");
            }

            if (mode != "buy" && mode != "sell")
            {
                throw new BridgeException(400, "mode is buy or sell");
            }

            bool buying = mode == "buy";

            // what to say is worked out before waiting a turn, so a wrong vendor is refused at once
            string words = OnGame
            (
                () =>
                {
                    Mobile vendor = _world.Mobiles.Get(vendorSerial) ?? throw new BridgeException(404, "no such vendor nearby");

                    return VendorName(vendor, rules).Name + " " + mode;
                }
            );

            WaitForActionSlot("shop");

            (long before, long listsBefore) = OnGame
            (
                () =>
                {
                    Mobile vendor = _world.Mobiles.Get(vendorSerial) ?? throw new BridgeException(404, "no such vendor nearby");
                    int distance = vendor.Distance;

                    if (distance > SHOP_RANGE)
                    {
                        throw new BridgeException(409, $"too far from the vendor ({distance} tiles; at most {SHOP_RANGE})");
                    }

                    CheckNobodyElse(rules);
                    CloseShop();
                    LogAction($"say \"{words}\"", vendorSerial);
                    long id = _lastMessageId;
                    long lists = buying ? _buyLists : _sellLists;
                    GameActions.Say(words);

                    return (id, lists);
                }
            );

            bool shown = WaitFor
            (
                () => (buying ? _buyLists : _sellLists) > listsBefore && ShopOpen(vendorSerial, buying) || HasMessageFrom(vendorSerial, before),
                SHOP_TIMEOUT
            );

            // no halt when he doesn't answer: a vendor who didn't hear isn't the server going quiet, and a halted bridge
            // would leave the character stranded in town (the agent goes home instead)

            // his words can come a moment before the window, and the window's contents right after it
            WaitFor(() => ShopOpen(vendorSerial, buying), SETTLE_TIME * 2);
            Thread.Sleep(SETTLE_TIME);
            PaceFromNow();

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        w.WriteStartObject();
                        w.WriteString("said", words);
                        w.WriteBoolean("answered", shown);
                        WriteShopFields(w);
                        WriteMessagesSince(w, before, 0);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // asks for each person's paperdoll and reads the title in it; the paperdoll is closed again at once
        private byte[] Paperdolls(List<uint> serials)
        {
            var results = new List<(uint Serial, bool Answered, string Title)>();

            foreach (uint serial in serials)
            {
                if (!SerialHelper.IsMobile(serial))
                {
                    throw new BridgeException(400, $"{Hex(serial)} is not a person");
                }

                WaitForActionSlot("paperdoll");
                PaperDollGump ownBefore = OnGame(() => UIManager.GetGump<PaperDollGump>(_world.Player.Serial));

                long before = OnGame
                (
                    () =>
                    {
                        Mobile m = _world.Mobiles.Get(serial) ?? throw new BridgeException(404, $"no such person nearby: {Hex(serial)}");

                        if (m.Distance > PAPERDOLL_RANGE)
                        {
                            throw new BridgeException(409, $"{Hex(serial)} is too far off ({m.Distance} tiles)");
                        }

                        if (_world.Player.InWarMode)
                        {
                            throw new BridgeException(409, "in war mode a double-click on someone is an attack");
                        }

                        LogAction("paperdoll", serial);
                        long count = _paperdollCount;
                        // a plain double-click shows someone's paperdoll; with the paperdoll flag (0x80000000, as the
                        // client's own OpenPaperdoll sends it) this server shows the character's own instead (2026-11-08)
                        NetClient.Socket.Send_DoubleClick(serial);

                        return count;
                    }
                );

                // someone may walk off before it comes: no halt (a halt in town would strand the character)
                bool answered = WaitFor(() => _paperdolls.TryGetValue(serial, out long at) && at > before, PAPERDOLL_TIMEOUT);
                Thread.Sleep(SETTLE_TIME / 3);

                string title = OnGame
                (
                    () =>
                    {
                        UIManager.GetGump<PaperDollGump>(serial)?.Dispose();

                        if (ownBefore == null)
                        {
                            UIManager.GetGump<PaperDollGump>(_world.Player.Serial)?.Dispose();
                        }

                        return _world.Mobiles.Get(serial)?.Title?.Trim('\0', ' ');
                    }
                );

                results.Add((serial, answered, title));
            }

            return Json
            (
                w =>
                {
                    w.WriteStartArray();

                    foreach ((uint serial, bool answered, string title) in results)
                    {
                        w.WriteStartObject();
                        w.WriteString("serial", Hex(serial));
                        w.WriteBoolean("answered", answered);
                        w.WriteString("title", title);
                        w.WriteEndObject();
                    }

                    w.WriteEndArray();
                }
            );
        }

        // on the game thread
        private bool ShopOpen(uint vendor, bool buying) => UIManager.GetGump<ShopGump>(vendor) is ShopGump g && !g.IsDisposed && g.IsBuyGump == buying;

        private bool CloseShop()
        {
            ShopGump gump = UIManager.GetGump<ShopGump>();

            if (gump == null)
            {
                return false;
            }

            gump.Dispose();

            return true;
        }

        // on the game thread: what the open buy window offers (the vendor's shop containers, priced by the buy list)
        private List<(Item Item, uint Price, string Name)> BuyOffer(uint vendorSerial)
        {
            var offer = new List<(Item, uint, string)>();
            Mobile vendor = _world.Mobiles.Get(vendorSerial);

            if (vendor == null)
            {
                return offer;
            }

            foreach (Layer layer in new[] { Layer.ShopBuyRestock, Layer.ShopBuy })
            {
                Item box = vendor.FindItemByLayer(layer);

                for (LinkedObject o = box?.Items; o != null; o = o.Next)
                {
                    if (o is Item it && it.Price > 0)
                    {
                        offer.Add((it, it.Price, string.IsNullOrEmpty(it.Name) ? it.ItemData.Name : it.Name));
                    }
                }
            }

            return offer;
        }

        // on the game thread: everything carried of the given kinds (amounts counted), and the gold
        private (int Goods, int Gold, int Items) Carried(HashSet<ushort> goods)
        {
            int count = 0, gold = 0, items = 0;
            Item pack = _world.Player.FindItemByLayer(Layer.Backpack);

            void Walk(Item container, int depth)
            {
                for (LinkedObject o = container?.Items; o != null; o = o.Next)
                {
                    if (o is not Item it)
                    {
                        continue;
                    }

                    items++;

                    if (goods.Contains(it.Graphic))
                    {
                        count += Math.Max(1, (int)it.Amount);
                    }

                    if (it.Graphic == GOLD)
                    {
                        gold += it.Amount;
                    }

                    if (depth < MAX_DEPTH)
                    {
                        Walk(it, depth + 1);
                    }
                }
            }

            Walk(pack, 1);

            return (count, gold, items);
        }

        private byte[] Deal(bool buying, List<(uint Serial, int Amount)> deal)
        {
            Rules rules = RequireRules();

            if (rules.Vendors.Count == 0 || rules.Goods.Count == 0)
            {
                throw new BridgeException(403, "the rules name no vendors or goods");
            }

            WaitForActionSlot(buying ? "buy" : "sell");

            (long before, uint vendor, int asked, int total, int goodsBefore, int goldBefore, HashSet<uint> selling) = OnGame
            (
                () =>
                {
                    ShopGump gump = UIManager.GetGump<ShopGump>();

                    if (gump == null || gump.IsDisposed || gump.IsBuyGump != buying)
                    {
                        throw new BridgeException(409, $"no {(buying ? "buy" : "sell")} window is open (/shop first)");
                    }

                    uint v = gump.LocalSerial;
                    Mobile m = _world.Mobiles.Get(v) ?? throw new BridgeException(404, "the vendor is gone");
                    VendorName(m, rules); // still one the rules allow

                    if (m.Distance > SHOP_RANGE + 1)
                    {
                        throw new BridgeException(409, $"too far from the vendor ({m.Distance} tiles)");
                    }

                    int count = 0, price = 0;
                    var sold = new HashSet<uint>();
                    var items = new Tuple<uint, ushort>[deal.Count];

                    for (int i = 0; i < deal.Count; i++)
                    {
                        (uint serial, int amount) = deal[i];
                        ushort graphic;
                        int have;
                        uint each;

                        if (buying)
                        {
                            (Item item, uint p, string name)? found = null;

                            foreach ((Item item, uint p, string name) o in BuyOffer(v))
                            {
                                if (o.item.Serial == serial)
                                {
                                    found = o;
                                }
                            }

                            if (found == null)
                            {
                                throw new BridgeException(404, $"{Hex(serial)} is not in his buy window");
                            }

                            graphic = found.Value.item.Graphic;
                            have = Math.Max(1, (int)found.Value.item.Amount);
                            each = found.Value.p;
                        }
                        else
                        {
                            ShopEntry entry = _sellVendor == v ? _sellList.Find(e => e.Serial == serial) : null;

                            if (entry == null)
                            {
                                throw new BridgeException(404, $"{Hex(serial)} is not in his sell window");
                            }

                            Item own = _world.Items.Get(serial);

                            if (own == null || !IsCarried(own))
                            {
                                throw new BridgeException(403, $"{Hex(serial)} is not carried");
                            }

                            graphic = entry.Graphic;
                            have = Math.Max(1, (int)entry.Amount);
                            each = entry.Price;
                            sold.Add(serial);
                        }

                        if (!rules.Goods.Contains(graphic))
                        {
                            throw new BridgeException(403, $"{Hex(serial)} ({Hex(graphic)}) is not among the rules' goods");
                        }

                        if (amount > have)
                        {
                            throw new BridgeException(409, $"{Hex(serial)}: {amount} asked, {have} there");
                        }

                        count += amount;
                        price += (int)each * amount;
                        items[i] = new Tuple<uint, ushort>(serial, (ushort)amount);
                    }

                    (int goods, int gold, int carriedItems) = Carried(rules.Goods);

                    if (buying && price > rules.Spend)
                    {
                        throw new BridgeException(403, $"{price} gold is more than the rules let him spend at once ({rules.Spend})");
                    }

                    if (buying && price > gold)
                    {
                        throw new BridgeException(409, $"{price} gold asked, {gold} carried");
                    }

                    LogAction($"{(buying ? "buy" : "sell")} {count} for {price} gold", v);
                    long id = _lastMessageId;

                    if (buying)
                    {
                        NetClient.Socket.Send_BuyRequest(v, items);
                    }
                    else
                    {
                        NetClient.Socket.Send_SellRequest(v, items);
                    }

                    gump.Dispose();

                    return (id, v, count, price, goods, gold, sold);
                }
            );

            // the goods land (or leave) one by one: wait for the first change or his word, then until it settles
            Func<(int Goods, int Gold, int Items)> now = () => Carried(rules.Goods);
            bool answered = WaitFor
            (
                () =>
                {
                    var (goods, gold, _) = now();

                    return goods != goodsBefore || gold != goldBefore || HasMessageFrom(vendor, before);
                },
                SHOP_DEAL_TIMEOUT
            );

            // (no halt either way: the answer below says what happened, and the agent goes home if nothing did)
            DateTime end = DateTime.UtcNow.AddMilliseconds(SHOP_DEAL_TIMEOUT);
            (int Goods, int Gold, int Items) last = OnGame(now);
            DateTime changed = DateTime.UtcNow;

            while (DateTime.UtcNow < end)
            {
                bool done = buying ? last.Goods - goodsBefore >= asked : goodsBefore - last.Goods >= asked;

                if (done || (DateTime.UtcNow - changed).TotalMilliseconds > SHOP_QUIET)
                {
                    break;
                }

                Thread.Sleep(POLL_INTERVAL * 2);
                (int Goods, int Gold, int Items) next = OnGame(now);

                if (next != last)
                {
                    last = next;
                    changed = DateTime.UtcNow;
                }
            }

            Thread.Sleep(SETTLE_TIME);
            PaceFromNow();

            return OnGame
            (
                () => Json
                (
                    w =>
                    {
                        (int goods, int gold, int carriedItems) = Carried(rules.Goods);
                        w.WriteStartObject();
                        w.WriteString("vendor", Hex(vendor));
                        w.WriteBoolean("answered", answered);
                        w.WriteNumber("asked", asked);
                        w.WriteNumber("price", total);
                        w.WriteNumber(buying ? "bought" : "sold", buying ? goods - goodsBefore : goodsBefore - goods);
                        w.WriteNumber("goldBefore", goldBefore);
                        w.WriteNumber("gold", gold);
                        w.WriteNumber("carriedItems", carriedItems);

                        if (!buying)
                        {
                            int left = 0;

                            foreach (uint s in selling)
                            {
                                if (_world.Items.Get(s) is Item it && IsCarried(it))
                                {
                                    left++;
                                }
                            }

                            w.WriteNumber("stillCarried", left);
                        }

                        WriteMessagesSince(w, before, 0);
                        w.WriteEndObject();
                    }
                )
            );
        }

        // ---- json (game thread) ----

        private void WriteShop(Utf8JsonWriter w)
        {
            w.WriteStartObject();
            WriteShopFields(w);
            w.WriteEndObject();
        }

        private void WriteShopFields(Utf8JsonWriter w)
        {
            ShopGump gump = UIManager.GetGump<ShopGump>();

            w.WriteBoolean("open", gump != null);

            if (gump == null)
            {
                return;
            }

            uint vendor = gump.LocalSerial;
            w.WriteString("mode", gump.IsBuyGump ? "buy" : "sell");
            w.WriteString("vendor", Hex(vendor));

            if (_world.Mobiles.Get(vendor) is Mobile m)
            {
                w.WriteString("vendorName", m.Name);
                w.WriteNumber("distance", m.Distance);
            }

            w.WriteStartArray("items");

            if (gump.IsBuyGump)
            {
                foreach ((Item item, uint price, string name) in BuyOffer(vendor))
                {
                    w.WriteStartObject();
                    w.WriteString("serial", Hex(item.Serial));
                    w.WriteString("graphic", Hex(item.Graphic));
                    w.WriteNumber("hue", item.Hue);
                    w.WriteNumber("amount", Math.Max(1, (int)item.Amount));
                    w.WriteNumber("price", price);
                    w.WriteString("name", name);
                    w.WriteEndObject();
                }
            }
            else if (_sellVendor == vendor)
            {
                foreach (ShopEntry e in _sellList)
                {
                    w.WriteStartObject();
                    w.WriteString("serial", Hex(e.Serial));
                    w.WriteString("graphic", Hex(e.Graphic));
                    w.WriteNumber("hue", e.Hue);
                    w.WriteNumber("amount", e.Amount);
                    w.WriteNumber("price", e.Price);
                    w.WriteString("name", e.Name);
                    w.WriteEndObject();
                }
            }

            w.WriteEndArray();
        }

        private sealed class ShopEntry
        {
            public uint Serial;
            public ushort Graphic, Hue, Amount, Price;
            public string Name;
        }
    }
}
