// Minimal stand-ins for the game types BuffTracker uses, so it can run against recorded logs.
using ClassicUO.Game.Data;
using ClassicUO.Game.GameObjects;
using System;

namespace ClassicUO
{
    internal static class Time { public static uint Ticks; }
}

namespace ClassicUO.Configuration
{
    internal sealed class Profile { public bool TrackBuffs { get; set; } = true; }
    internal static class ProfileManager { public static Profile CurrentProfile { get; set; } = new Profile(); }
}

namespace ClassicUO.Game.Data
{
    internal sealed class Skill
    {
        public Skill(string name, float value) { Name = name; Value = value; }
        public string Name { get; }
        public float Value { get; }
    }
}

namespace ClassicUO.Game.GameObjects
{
    internal sealed class Item { public uint Serial; }

    internal sealed class PlayerMobile
    {
        public uint Serial;
        public ushort X, Y;
        public Skill[] Skills = Array.Empty<Skill>();
        public Action<string> Log;

        public Item FindItemByLayer(Layer layer) => null;
        public void AddBuff(BuffIconType type, ushort graphic, uint time, string text) =>
            Log($"+ {type,-16} {(time == 0 ? "no timer" : time + " s"),-9} {text.Replace("<left>", "").Replace("</left>", "").Replace("\n", " | ")}");
        public void RemoveBuff(BuffIconType type) => Log($"- {type}");
    }
}

namespace ClassicUO.Game
{
    internal sealed class World { public PlayerMobile Player; }
}

namespace ClassicUO.Game.UI.Gumps
{
    internal sealed class BuffGump { public void RequestUpdateContents() { } }
}

namespace ClassicUO.Game.Managers
{
    internal static class UIManager { public static T GetGump<T>() where T : class => null; }
}
