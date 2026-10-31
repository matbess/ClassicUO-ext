// SPDX-License-Identifier: BSD-2-Clause

using ClassicUO.Configuration;
using ClassicUO.Game.Data;
using ClassicUO.Game.GameObjects;
using ClassicUO.Game.UI.Gumps;
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text;

namespace ClassicUO.Game.Managers
{
    // Fills the buff bar on shards that never send buff packets (0xDF), such as UOSA.
    // Effects are worked out from what the server does send about the player: stat and armor
    // changes, status flags, personal light, body changes, spell sounds and effects, words of
    // power and system messages. The sounds, messages and durations were measured on UOSA.
    internal sealed class BuffTracker
    {
        private enum Kind : byte
        {
            None,
            Bless,
            Strength,
            Agility,
            Cunning,
            StrengthPotion,
            AgilityPotion,
            Curse,
            Weaken,
            Clumsy,
            Feeblemind,
            Protection,
            ArchProtection
        }

        private struct Slot
        {
            public int Offset;
            public Kind Owner;
            public uint Start;
        }

        private struct Shown
        {
            public uint End;
            public string Text;
        }

        private const int STR = 0, DEX = 1, INT = 2, ARMOR = 3;

        private const uint SYSTEM_SERIAL = 0xFFFF_FFFF;

        // how long a stat change waits for the sound or effect that explains it
        private const int CAUSE_WINDOW = 300;
        // how long after its words of power a spell can land; targeted spells wait for the target
        private const int WORDS_WINDOW = 30000;
        // stat or armor changes this close to an equipment change come from the equipment
        private const int EQUIP_WINDOW = 1500;
        // how long past its expected end an effect is kept when its end is never seen
        private const int GRACE = 10000;
        // a stat change this small is a skill gain or loss, not a spell
        private const int SMALL_CHANGE = 2;

        private const int BUFF_SECONDS = 120;
        private const int CURSE_SECONDS = 45;
        private const int PARALYZE_MAX = 60000;
        private const int REACTIVE_ARMOR_MAX = 75000;
        private const int SOUND_RANGE = 2;

        private const ushort SOUND_CLUMSY = 0x01DF;
        private const ushort SOUND_FEEBLEMIND = 0x01E4;
        private const ushort SOUND_WEAKEN = 0x01E6;
        private const ushort SOUND_BLESS_CURSE = 0x01EA;
        private const ushort SOUND_CUNNING = 0x01EB;
        private const ushort SOUND_STRENGTH = 0x01EE;
        private const ushort SOUND_AGILITY = 0x028E;
        private const ushort SOUND_PROTECTION = 0x01F7;
        private const ushort SOUND_ARCH_PROTECTION = 0x0299;
        private const ushort SOUND_MAGIC_REFLECTION = 0x01E9;
        private const ushort SOUND_REACTIVE_ARMOR = 0x01F2; // also played by the heal spells
        private const ushort SOUND_REACTIVE_ARMOR_END = 0x005C;
        private const ushort SOUND_INVISIBILITY = 0x0203;
        private const ushort SOUND_STAT_POTION = 0x01E7;
        private const ushort SOUND_DRINK = 0x02D6;

        private const ushort EFFECT_REFLECT = 0x37B9;
        private const ushort EFFECT_MAGIC_REFLECTION = 0x375A;
        private const ushort EFFECT_REACTIVE_ARMOR = 0x376A;

        private const string WORDS_REACTIVE_ARMOR = "Flam Sanct";
        private const string WORDS_INVISIBILITY = "An Lor Xen";

        private static readonly Layer[] _equipmentLayers =
        {
            Layer.OneHanded, Layer.TwoHanded, Layer.Shoes, Layer.Pants, Layer.Shirt, Layer.Helmet,
            Layer.Gloves, Layer.Ring, Layer.Talisman, Layer.Necklace, Layer.Waist, Layer.Torso,
            Layer.Bracelet, Layer.Tunic, Layer.Earrings, Layer.Arms, Layer.Cloak, Layer.Robe,
            Layer.Skirt, Layer.Legs
        };

        private readonly World _world;
        private readonly Slot[] _slots = new Slot[4];
        private readonly int[] _stats = new int[4];
        private readonly int[] _pendingDelta = new int[4];
        private readonly List<(uint Time, ushort Id)> _sounds = new List<(uint, ushort)>();
        private readonly List<(uint Time, ushort Id)> _effects = new List<(uint, ushort)>();
        private readonly List<(uint Time, uint Caster, string Words)> _words = new List<(uint, uint, string)>();
        private readonly Dictionary<BuffIconType, Shown> _shown = new Dictionary<BuffIconType, Shown>();

        private uint _playerSerial;
        private bool _serverSendsBuffs;
        private bool _haveStats;
        private bool _hasPending;
        private uint _pendingTime;
        private bool _dirty;

        private bool _poisoned, _hidden, _invisible, _nightSight, _polymorphed, _dead;
        private bool _paralyzed, _magicReflection, _reactiveArmor;
        private uint _paralyzeStart, _reactiveArmorStart, _lastHealMessage;
        private int _reactiveArmorDuration; // ms, 0 when the caster's skill is unknown

        private bool _equipmentKnown;
        private uint _equipmentHash, _lastEquipmentCheck, _lastEquipmentChange;

        public BuffTracker(World world)
        {
            _world = world;
        }

        private static bool IsEnabled => ProfileManager.CurrentProfile?.TrackBuffs == true;

        public void OnPacket(ReadOnlySpan<byte> data)
        {
            PlayerMobile player = _world.Player;

            if (data.IsEmpty || player == null)
            {
                return;
            }

            if (data[0] == 0xDF)
            {
                // the server shows buffs itself
                _serverSendsBuffs = true;
                RemoveShown();

                return;
            }

            if (_serverSendsBuffs || !IsEnabled)
            {
                return;
            }

            if (player.Serial != _playerSerial)
            {
                Reset(player.Serial);
            }

            uint serial = player.Serial;
            uint now = Time.Ticks;

            switch (data[0])
            {
                case 0x11 when data.Length >= 66 && ReadUInt32(data, 3) == serial && data[42] >= 1: // status
                    OnStatus(ReadUInt16(data, 44), ReadUInt16(data, 46), ReadUInt16(data, 48), ReadUInt16(data, 62), now);

                    break;

                case 0x20 when data.Length >= 11 && ReadUInt32(data, 1) == serial: // update player
                    OnFlagsAndBody(data[10], ReadUInt16(data, 5), now);

                    break;

                case 0x77 when data.Length >= 16 && ReadUInt32(data, 1) == serial: // update mobile
                    OnFlagsAndBody(data[15], ReadUInt16(data, 5), now);

                    break;

                case 0x78 when data.Length >= 18 && ReadUInt32(data, 3) == serial: // mobile incoming
                    OnFlagsAndBody(data[17], ReadUInt16(data, 7), now);

                    break;

                case 0x4E when data.Length >= 6 && ReadUInt32(data, 1) == serial: // personal light, set by Night Sight
                    Set(ref _nightSight, data[5] != 0);

                    break;

                case 0x54 when data.Length >= 10 && IsNearPlayer(player, ReadUInt16(data, 6), ReadUInt16(data, 8)): // sound
                    OnSound(ReadUInt16(data, 2), now);

                    break;

                case 0x70:
                case 0xC0:
                case 0xC7:
                    // effects that stay on a mobile name it as the source
                    if (data.Length >= 12 && data[1] == 3 && ReadUInt32(data, 2) == serial)
                    {
                        OnEffect(ReadUInt16(data, 10), now);
                    }

                    break;

                case 0x1C when data.Length >= 44: // ascii speech
                    OnSpeech(ReadUInt32(data, 3), Encoding.ASCII.GetString(TrimAt(data.Slice(44), 1)).Trim(), now);

                    break;

                case 0xAE when data.Length >= 48: // unicode speech
                    OnSpeech(ReadUInt32(data, 3), Encoding.BigEndianUnicode.GetString(TrimAt(data.Slice(48), 2)).Trim(), now);

                    break;
            }
        }

        public void Update()
        {
            PlayerMobile player = _world.Player;

            if (player == null)
            {
                return;
            }

            if (_serverSendsBuffs || !IsEnabled)
            {
                RemoveShown();

                return;
            }

            if (player.Serial != _playerSerial)
            {
                Reset(player.Serial);
            }

            uint now = Time.Ticks;

            if (_hasPending && Elapsed(_pendingTime, now) >= CAUSE_WINDOW)
            {
                ResolvePending();
            }

            CheckEquipment(player, now);
            ExpireMissedEnds(now);

            if (_dirty)
            {
                Sync(player, now);
            }
        }

        private void OnStatus(int str, int dex, int intel, int armor, uint now)
        {
            if (!_haveStats)
            {
                _haveStats = true;
                _stats[STR] = str;
                _stats[DEX] = dex;
                _stats[INT] = intel;
                _stats[ARMOR] = armor;

                return;
            }

            if (_hasPending && Elapsed(_pendingTime, now) >= CAUSE_WINDOW)
            {
                ResolvePending();
            }

            Span<int> values = stackalloc int[4] { str, dex, intel, armor };

            for (int i = 0; i < values.Length; i++)
            {
                int delta = values[i] - _stats[i];

                if (delta == 0)
                {
                    continue;
                }

                if (!_hasPending)
                {
                    _hasPending = true;
                    _pendingTime = now;
                    Array.Clear(_pendingDelta);
                }

                _pendingDelta[i] += delta;
                _stats[i] = values[i];
            }
        }

        // Each stat holds one magic bonus or penalty at a time: a stronger effect replaces a weaker
        // one with a new timer, a weaker one changes nothing and an opposite one cancels it.
        private void ResolvePending()
        {
            _hasPending = false;

            uint time = _pendingTime;
            bool potion = HasSound(SOUND_STAT_POTION, time) || HasSound(SOUND_DRINK, time);
            bool sparkle = HasSpellEffect(time);
            bool equipment = _equipmentKnown && Math.Abs(Elapsed(_lastEquipmentChange, time)) < EQUIP_WINDOW;
            bool allStats = _pendingDelta[STR] != 0
                && Math.Sign(_pendingDelta[STR]) == Math.Sign(_pendingDelta[DEX])
                && Math.Sign(_pendingDelta[STR]) == Math.Sign(_pendingDelta[INT]);

            for (int i = 0; i < _slots.Length; i++)
            {
                int delta = _pendingDelta[i];

                if (delta == 0)
                {
                    continue;
                }

                ref Slot slot = ref _slots[i];
                int offset = slot.Offset + delta;
                Kind cause = FindCause(i, delta, time, potion, sparkle, allStats);

                if (cause != Kind.None)
                {
                    if (offset == 0)
                    {
                        // cancelled, e.g. Agility on Clumsy
                        slot = default;
                    }
                    else if (Math.Sign(offset) == Math.Sign(delta))
                    {
                        slot.Offset = offset;
                        slot.Owner = cause;
                        slot.Start = time;
                    }
                    else
                    {
                        // weakened but not cancelled
                        slot.Offset = offset;
                    }
                }
                else if (slot.Owner != Kind.None && offset == 0 && Elapsed(slot.Start, time) >= Duration(slot.Owner) - 5000)
                {
                    // ran out
                    slot = default;
                }
                else if (equipment || Math.Abs(delta) <= SMALL_CHANGE || slot.Owner == Kind.None)
                {
                    // the stat itself changed, the magic offset did not
                }
                else if (offset == 0)
                {
                    // ended early
                    slot = default;
                }
            }

            _dirty = true;
        }

        private Kind FindCause(int stat, int delta, uint time, bool potion, bool sparkle, bool allStats)
        {
            if (stat == ARMOR)
            {
                if (delta > 0 && HasSound(SOUND_ARCH_PROTECTION, time))
                {
                    return Kind.ArchProtection;
                }

                return delta > 0 && HasSound(SOUND_PROTECTION, time) ? Kind.Protection : Kind.None;
            }

            if (potion && delta > 0)
            {
                return stat == STR ? Kind.StrengthPotion : stat == DEX ? Kind.AgilityPotion : Kind.None;
            }

            if (HasSound(SOUND_BLESS_CURSE, time))
            {
                return delta > 0 ? Kind.Bless : Kind.Curse;
            }

            Kind single = SingleStatSpell(stat, delta);

            if (HasSound(SingleStatSound(single), time))
            {
                return single;
            }

            // a spell landed but its sound was missed or unknown, e.g. Mass Curse
            if (sparkle)
            {
                return allStats ? delta > 0 ? Kind.Bless : Kind.Curse : single;
            }

            return Kind.None;
        }

        private static Kind SingleStatSpell(int stat, int delta)
        {
            switch (stat)
            {
                case STR: return delta > 0 ? Kind.Strength : Kind.Weaken;
                case DEX: return delta > 0 ? Kind.Agility : Kind.Clumsy;
                default: return delta > 0 ? Kind.Cunning : Kind.Feeblemind;
            }
        }

        private static ushort SingleStatSound(Kind kind)
        {
            switch (kind)
            {
                case Kind.Strength: return SOUND_STRENGTH;
                case Kind.Agility: return SOUND_AGILITY;
                case Kind.Cunning: return SOUND_CUNNING;
                case Kind.Weaken: return SOUND_WEAKEN;
                case Kind.Clumsy: return SOUND_CLUMSY;
                default: return SOUND_FEEBLEMIND;
            }
        }

        private void OnFlagsAndBody(byte flags, ushort body, uint now)
        {
            if (IsGhost(body))
            {
                // dying ends every effect
                if (!_dead)
                {
                    _dead = true;
                    ClearEffects();
                }

                return;
            }

            _dead = false;

            Set(ref _poisoned, (flags & 0x04) != 0);
            Set(ref _polymorphed, !IsHumanBody(body));

            bool hidden = (flags & 0x80) != 0;

            if (hidden && !_hidden)
            {
                // the Hiding skill sets the same flag, the spell comes with its words and sound
                Set(ref _invisible, HasSound(SOUND_INVISIBILITY, now) || FindWords(WORDS_INVISIBILITY, now, out _));
            }
            else if (!hidden)
            {
                Set(ref _invisible, false);
            }

            _hidden = hidden;
        }

        private void OnSound(ushort sound, uint now)
        {
            _sounds.Add((now, sound));

            switch (sound)
            {
                // the spell's effect on the player arrives just before its sound; a nearby
                // player's spell plays the same sound without it
                case SOUND_MAGIC_REFLECTION when HasEffect(EFFECT_MAGIC_REFLECTION, now):
                    Set(ref _magicReflection, true);

                    break;

                case SOUND_REACTIVE_ARMOR when HasEffect(EFFECT_REACTIVE_ARMOR, now):
                    // the heal spells play the same sound, but announce how much they healed first
                    if (Elapsed(_lastHealMessage, now) > CAUSE_WINDOW && FindWords(WORDS_REACTIVE_ARMOR, now, out uint caster))
                    {
                        RemoveWords(WORDS_REACTIVE_ARMOR);
                        _reactiveArmor = true;
                        _reactiveArmorStart = now;
                        _reactiveArmorDuration = caster == _playerSerial ? ReactiveArmorDuration() : 0;
                        _dirty = true;
                    }

                    break;

                case SOUND_REACTIVE_ARMOR_END:
                    if (_reactiveArmor && Elapsed(_reactiveArmorStart, now) >= 5000)
                    {
                        Set(ref _reactiveArmor, false);
                    }

                    break;
            }
        }

        private void OnEffect(ushort graphic, uint now)
        {
            _effects.Add((now, graphic));

            if (graphic == EFFECT_REFLECT)
            {
                // a reflected spell uses Magic Reflection up
                Set(ref _magicReflection, false);
            }
        }

        private void OnSpeech(uint serial, string text, uint now)
        {
            if (serial == SYSTEM_SERIAL || serial == 0)
            {
                OnSystemMessage(text, now);
            }
            else if (text == WORDS_REACTIVE_ARMOR || text == WORDS_INVISIBILITY)
            {
                _words.Add((now, serial, text));
            }
        }

        private void OnSystemMessage(string text, uint now)
        {
            if (text == "You cannot move!")
            {
                _paralyzed = true;
                _paralyzeStart = now;
                _dirty = true;
            }
            else if (text == "You can move!")
            {
                Set(ref _paralyzed, false);
            }
            else if (text.EndsWith("points of damage have been healed."))
            {
                _lastHealMessage = now;
            }
        }

        private void CheckEquipment(PlayerMobile player, uint now)
        {
            if (_equipmentKnown && Elapsed(_lastEquipmentCheck, now) < 100)
            {
                return;
            }

            _lastEquipmentCheck = now;

            uint hash = 17;

            foreach (Layer layer in _equipmentLayers)
            {
                hash = unchecked(hash * 31 + (player.FindItemByLayer(layer)?.Serial ?? 0));
            }

            if (_equipmentKnown && hash != _equipmentHash)
            {
                _lastEquipmentChange = now;
            }

            _equipmentHash = hash;
            _equipmentKnown = true;
        }

        private void ExpireMissedEnds(uint now)
        {
            for (int i = 0; i < _slots.Length; i++)
            {
                ref Slot slot = ref _slots[i];

                if (slot.Owner != Kind.None && Elapsed(slot.Start, now) > Duration(slot.Owner) + GRACE)
                {
                    // the end was never seen, so take the current value as the stat itself
                    slot = default;
                    _dirty = true;
                }
            }

            if (_paralyzed && Elapsed(_paralyzeStart, now) > PARALYZE_MAX)
            {
                Set(ref _paralyzed, false);
            }

            if (_reactiveArmor)
            {
                int limit = _reactiveArmorDuration > 0 ? _reactiveArmorDuration + 5000 : REACTIVE_ARMOR_MAX;

                if (Elapsed(_reactiveArmorStart, now) > limit)
                {
                    Set(ref _reactiveArmor, false);
                }
            }

            _sounds.RemoveAll(s => Elapsed(s.Time, now) > 2000);
            _effects.RemoveAll(e => Elapsed(e.Time, now) > 2000);
            _words.RemoveAll(w => Elapsed(w.Time, now) > WORDS_WINDOW);
        }

        private void Sync(PlayerMobile player, uint now)
        {
            _dirty = false;

            Dictionary<BuffIconType, Shown> wanted = new Dictionary<BuffIconType, Shown>();

            for (Kind kind = Kind.Bless; kind <= Kind.ArchProtection; kind++)
            {
                AddStatEffect(wanted, kind);
            }

            if (_poisoned)
            {
                wanted[BuffIconType.Poison] = new Shown { Text = "Poisoned" };
            }

            if (_paralyzed)
            {
                wanted[BuffIconType.Paralyze] = new Shown { Text = "Paralyzed" };
            }

            if (_invisible)
            {
                wanted[BuffIconType.Invisibility] = new Shown { Text = "Invisible" };
            }

            if (_nightSight)
            {
                wanted[BuffIconType.NightSight] = new Shown { Text = "Night Sight" };
            }

            if (_polymorphed)
            {
                wanted[BuffIconType.Polymorph] = new Shown { Text = "Polymorphed" };
            }

            if (_magicReflection)
            {
                wanted[BuffIconType.MagicReflection] = new Shown { Text = "Magic Reflection\nUsed up by the next spell that hits you" };
            }

            if (_reactiveArmor)
            {
                wanted[BuffIconType.ReactiveArmor] = new Shown
                {
                    End = _reactiveArmorDuration > 0 ? _reactiveArmorStart + (uint)_reactiveArmorDuration : 0,
                    Text = "Reactive Armor"
                };
            }

            bool changed = false;

            foreach (BuffIconType type in new List<BuffIconType>(_shown.Keys))
            {
                if (!wanted.ContainsKey(type))
                {
                    player.RemoveBuff(type);
                    _shown.Remove(type);
                    changed = true;
                }
            }

            foreach (KeyValuePair<BuffIconType, Shown> pair in wanted)
            {
                if (_shown.TryGetValue(pair.Key, out Shown shown) && shown.End == pair.Value.End && shown.Text == pair.Value.Text)
                {
                    continue;
                }

                ushort graphic = Graphic(pair.Key);

                if (graphic == 0)
                {
                    continue;
                }

                uint seconds = pair.Value.End == 0 ? 0 : (uint)Math.Max(1, (Elapsed(now, pair.Value.End) + 999) / 1000);

                player.AddBuff(pair.Key, graphic, seconds, $"<left>{pair.Value.Text}</left>");
                _shown[pair.Key] = pair.Value;
                changed = true;
            }

            if (changed)
            {
                UIManager.GetGump<BuffGump>()?.RequestUpdateContents();
            }
        }

        private void AddStatEffect(Dictionary<BuffIconType, Shown> wanted, Kind kind)
        {
            StringBuilder text = null;
            uint end = 0;

            for (int i = 0; i < _slots.Length; i++)
            {
                Slot slot = _slots[i];

                if (slot.Owner != kind || slot.Offset == 0)
                {
                    continue;
                }

                if (text == null)
                {
                    text = new StringBuilder(Name(kind)).Append('\n');
                }
                else
                {
                    text.Append(", ");
                }

                text.Append(slot.Offset > 0 ? "+" : "-").Append(Math.Abs(slot.Offset)).Append(' ').Append(StatName(i));

                uint slotEnd = slot.Start + (uint)Duration(kind);

                if (end == 0 || Elapsed(end, slotEnd) > 0)
                {
                    end = slotEnd;
                }
            }

            if (text != null)
            {
                wanted[Icon(kind)] = new Shown { End = end, Text = text.ToString() };
            }
        }

        private void ClearEffects()
        {
            Array.Clear(_slots);
            _paralyzed = _magicReflection = _reactiveArmor = _invisible = _polymorphed = _poisoned = false;
            _dirty = true;
        }

        private void Reset(uint serial)
        {
            // a new player object starts with no buffs, so there is nothing to remove from it
            _playerSerial = serial;
            _haveStats = _hasPending = _equipmentKnown = _dead = false;
            _hidden = _nightSight = false;
            ClearEffects();
            _sounds.Clear();
            _effects.Clear();
            _words.Clear();
            _shown.Clear();
        }

        private void RemoveShown()
        {
            if (_shown.Count == 0)
            {
                return;
            }

            foreach (BuffIconType type in _shown.Keys)
            {
                _world.Player?.RemoveBuff(type);
            }

            _shown.Clear();
            _dirty = true;
            UIManager.GetGump<BuffGump>()?.RequestUpdateContents();
        }

        private int ReactiveArmorDuration()
        {
            // fits UOSA: 67 s at 100 Magery, 41 s at 57
            float magery = 0;

            foreach (Skill skill in _world.Player.Skills)
            {
                if (skill != null && skill.Name == "Magery")
                {
                    magery = skill.Value;

                    break;
                }
            }

            return (int)((7 + 0.6f * magery) * 1000);
        }

        private bool HasSound(ushort sound, uint time)
        {
            foreach ((uint t, ushort id) in _sounds)
            {
                if (id == sound && Math.Abs(Elapsed(time, t)) <= CAUSE_WINDOW)
                {
                    return true;
                }
            }

            return false;
        }

        private bool HasEffect(ushort graphic, uint time)
        {
            foreach ((uint t, ushort id) in _effects)
            {
                if (id == graphic && Math.Abs(Elapsed(time, t)) <= CAUSE_WINDOW)
                {
                    return true;
                }
            }

            return false;
        }

        // the sparkles curses, buffs and potions leave on the player
        private bool HasSpellEffect(uint time) =>
            HasEffect(0x3779, time) || HasEffect(0x374A, time) || HasEffect(0x375A, time) || HasEffect(0x373A, time);

        // the player's own words win over anyone else's
        private bool FindWords(string words, uint now, out uint caster)
        {
            caster = 0;

            for (int i = _words.Count - 1; i >= 0; i--)
            {
                if (_words[i].Words != words || Elapsed(_words[i].Time, now) > WORDS_WINDOW)
                {
                    continue;
                }

                if (_words[i].Caster == _playerSerial)
                {
                    caster = _playerSerial;

                    return true;
                }

                if (caster == 0)
                {
                    caster = _words[i].Caster;
                }
            }

            return caster != 0;
        }

        private void RemoveWords(string words) => _words.RemoveAll(w => w.Words == words);

        private void Set(ref bool field, bool value)
        {
            if (field != value)
            {
                field = value;
                _dirty = true;
            }
        }

        private static int Duration(Kind kind)
        {
            switch (kind)
            {
                case Kind.Curse:
                case Kind.Weaken:
                case Kind.Clumsy:
                case Kind.Feeblemind:
                    return CURSE_SECONDS * 1000;

                default:
                    return BUFF_SECONDS * 1000;
            }
        }

        private static BuffIconType Icon(Kind kind)
        {
            switch (kind)
            {
                case Kind.Bless: return BuffIconType.Bless;
                case Kind.Strength:
                case Kind.StrengthPotion: return BuffIconType.Strength;
                case Kind.Agility:
                case Kind.AgilityPotion: return BuffIconType.Agility;
                case Kind.Cunning: return BuffIconType.Cunning;
                case Kind.Curse: return BuffIconType.Curse;
                case Kind.Weaken: return BuffIconType.Weaken;
                case Kind.Clumsy: return BuffIconType.Clumsy;
                case Kind.Feeblemind: return BuffIconType.FeebleMind;
                case Kind.Protection: return BuffIconType.Protection;
                default: return BuffIconType.ArchProtection;
            }
        }

        private static string Name(Kind kind)
        {
            switch (kind)
            {
                case Kind.StrengthPotion: return "Strength potion";
                case Kind.AgilityPotion: return "Agility potion";
                case Kind.ArchProtection: return "Arch Protection";
                default: return kind.ToString();
            }
        }

        private static string StatName(int stat)
        {
            switch (stat)
            {
                case STR: return "Str";
                case DEX: return "Dex";
                case INT: return "Int";
                default: return "armor";
            }
        }

        private static ushort Graphic(BuffIconType type)
        {
            const ushort BUFF_ICON_START = 0x03E9;
            const ushort BUFF_ICON_START_NEW = 0x466;

            ushort iconID =
                (ushort)type >= BUFF_ICON_START_NEW
                    ? (ushort)(type - (BUFF_ICON_START_NEW - 125))
                    : (ushort)((ushort)type - BUFF_ICON_START);

            return iconID < BuffTable.Table.Length ? BuffTable.Table[iconID] : (ushort)0;
        }

        private static bool IsGhost(ushort body) =>
            body == 0x0192 || body == 0x0193 || body == 0x025F || body == 0x0260 || body == 0x02B6 || body == 0x02B7;

        private static bool IsHumanBody(ushort body) =>
            body == 0x0190 || body == 0x0191 || body == 0x025D || body == 0x025E || body == 0x029A || body == 0x029B || body == 0x03DB;

        private static bool IsNearPlayer(PlayerMobile player, ushort x, ushort y) =>
            Math.Abs(player.X - x) <= SOUND_RANGE && Math.Abs(player.Y - y) <= SOUND_RANGE;

        // milliseconds from one tick count to another, negative if "to" is earlier
        private static int Elapsed(uint from, uint to) => unchecked((int)(to - from));

        private static ReadOnlySpan<byte> TrimAt(ReadOnlySpan<byte> data, int charSize)
        {
            for (int i = 0; i + charSize <= data.Length; i += charSize)
            {
                if (data[i] == 0 && (charSize == 1 || data[i + 1] == 0))
                {
                    return data.Slice(0, i);
                }
            }

            return data.Slice(0, data.Length - data.Length % charSize);
        }

        private static uint ReadUInt32(ReadOnlySpan<byte> data, int offset) => BinaryPrimitives.ReadUInt32BigEndian(data.Slice(offset));

        private static ushort ReadUInt16(ReadOnlySpan<byte> data, int offset) => BinaryPrimitives.ReadUInt16BigEndian(data.Slice(offset));
    }
}
