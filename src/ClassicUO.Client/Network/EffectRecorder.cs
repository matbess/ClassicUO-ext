// SPDX-License-Identifier: BSD-2-Clause

using ClassicUO.Configuration;
using ClassicUO.Game;
using ClassicUO.Game.Data;
using ClassicUO.Utility;
using ClassicUO.Utility.Logging;
using System;
using System.Buffers.Binary;
using System.IO;
using System.Text;

namespace ClassicUO.Network
{
    // Diagnostic recorder for building a client-side buff/debuff tracker.
    // Writes the server packets that reveal spell effects on the player: stats, status flags,
    // effects and sounds around the player, light level, words of power and system messages.
    // Packets sent by the client and ordinary chat are never written.
    internal static class EffectRecorder
    {
        private const uint SYSTEM_SERIAL = 0xFFFF_FFFF;
        private const int SOUND_RANGE = 2;

        private static StreamWriter _writer;
        private static string _characterName;

        public static void Record(World world, ReadOnlySpan<byte> data)
        {
            Profile profile = ProfileManager.CurrentProfile;

            if (profile == null || !profile.RecordEffects)
            {
                Close();

                return;
            }

            // the player briefly disappears while logging in; keep the same file
            if (world?.Player == null || data.IsEmpty)
            {
                return;
            }

            if (!ShouldRecord(world, data, out string text))
            {
                return;
            }

            StreamWriter writer = GetWriter(profile.CharacterName);

            if (writer == null)
            {
                return;
            }

            writer.Write(DateTime.Now.ToString("HH:mm:ss.fff"));
            writer.Write(' ');
            writer.Write(data[0].ToString("X2"));
            writer.Write(' ');
            writer.Write(Convert.ToHexString(data));

            if (text != null)
            {
                writer.Write(" \"");
                writer.Write(text);
                writer.Write('"');
            }

            writer.WriteLine();
        }

        public static void Close()
        {
            _writer?.Dispose();
            _writer = null;
            _characterName = null;
        }

        private static bool ShouldRecord(World world, ReadOnlySpan<byte> data, out string text)
        {
            text = null;
            uint player = world.Player.Serial;

            switch (data[0])
            {
                // fixed size, serial at offset 1
                case 0x20: // update player
                case 0x2D: // mobile attributes
                case 0x4E: // personal light level
                case 0x6E: // character animation
                case 0x77: // update mobile
                case 0xA1: // update hits
                case 0xA2: // update mana
                case 0xA3: // update stamina
                case 0xE2: // new character animation
                    return data.Length >= 5 && ReadUInt32(data, 1) == player;

                // variable size, serial at offset 3
                case 0x11: // status
                case 0x16: // new health bar status
                case 0x17: // health bar status
                case 0x78: // mobile incoming
                    return data.Length >= 7 && ReadUInt32(data, 3) == player;

                case 0x4F: // global light level
                case 0xDF: // buffs and debuffs
                    return true;

                case 0x70: // graphic effect
                case 0xC0: // hued graphic effect
                case 0xC7: // particle effect
                    if (data.Length < 16)
                    {
                        return false;
                    }

                    return ReadUInt32(data, 2) == player
                        || ReadUInt32(data, 6) == player
                        || IsNearPlayer(world, ReadUInt16(data, 12), ReadUInt16(data, 14), 1);

                case 0x54: // sound
                    return data.Length >= 10 && IsNearPlayer(world, ReadUInt16(data, 6), ReadUInt16(data, 8), SOUND_RANGE);

                case 0x1C: // ascii speech
                    if (data.Length < 44)
                    {
                        return false;
                    }

                    text = Encoding.ASCII.GetString(TrimAt(data.Slice(44), 1)).Trim();

                    return IsWantedSpeech(ReadUInt32(data, 3), (MessageType)data[9], text, player);

                case 0xAE: // unicode speech
                    if (data.Length < 48)
                    {
                        return false;
                    }

                    text = Encoding.BigEndianUnicode.GetString(TrimAt(data.Slice(48), 2)).Trim();

                    return IsWantedSpeech(ReadUInt32(data, 3), (MessageType)data[9], text, player);

                case 0xC1: // cliloc message
                case 0xCC: // cliloc message with affix
                    if (data.Length < 10)
                    {
                        return false;
                    }

                    uint serial = ReadUInt32(data, 3);

                    return serial == SYSTEM_SERIAL || serial == 0 || serial == player || (MessageType)data[9] == MessageType.System;
            }

            return false;
        }

        private static bool IsWantedSpeech(uint serial, MessageType type, string text, uint player)
        {
            if (serial == SYSTEM_SERIAL || serial == 0 || type == MessageType.System || type == MessageType.Spell)
            {
                return true;
            }

            if (serial == player && type == MessageType.Label)
            {
                return true;
            }

            // words of power from anyone, so spells cast at the player can be matched to their effects
            return !string.IsNullOrEmpty(text) && SpellDefinition.WordToTargettype.ContainsKey(text);
        }

        private static bool IsNearPlayer(World world, ushort x, ushort y, int range)
        {
            return Math.Abs(world.Player.X - x) <= range && Math.Abs(world.Player.Y - y) <= range;
        }

        private static StreamWriter GetWriter(string characterName)
        {
            if (_writer != null && _characterName == characterName)
            {
                return _writer;
            }

            Close();

            try
            {
                // fill the words of power table
                _ = SpellsMagery.GetAllSpells;

                string name = string.IsNullOrEmpty(characterName) ? "unknown" : characterName;

                foreach (char c in Path.GetInvalidFileNameChars())
                {
                    name = name.Replace(c, '_');
                }

                string folder = FileSystemHelper.CreateFolderIfNotExists(CUOEnviroment.ExecutablePath, "Logs", "Effects");
                string path = Path.Combine(folder, $"effects_{name}_{DateTime.Now:yyyy-MM-dd_HH-mm-ss}.log");

                _writer = new StreamWriter(path, true, Encoding.UTF8) { AutoFlush = true };
                _characterName = characterName;

                _writer.WriteLine($"# ClassicUO {CUOEnviroment.Version} effect recorder, character {name}, started {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            }
            catch (Exception ex)
            {
                Log.Error($"Effect recorder could not open its log: {ex.Message}");
                _writer = null;
            }

            return _writer;
        }

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
