// Replays effect recorder logs through BuffTracker and prints every buff bar change.
// usage: replay <player serial hex> <magery> <log>...
using ClassicUO;
using ClassicUO.Game;
using ClassicUO.Game.Data;
using ClassicUO.Game.GameObjects;
using ClassicUO.Game.Managers;
using System;
using System.Globalization;
using System.IO;

uint serial = uint.Parse(args[0], NumberStyles.HexNumber);
float magery = float.Parse(args[1], CultureInfo.InvariantCulture);
uint clock = 0;
var player = new PlayerMobile { Serial = serial, Skills = new[] { new Skill("Magery", magery) } };
player.Log = s => Console.WriteLine($"{TimeSpan.FromMilliseconds(clock):hh\\:mm\\:ss\\.fff}  {s}");
var world = new World { Player = player };
var tracker = new BuffTracker(world);

for (int a = 2; a < args.Length; a++)
{
    Console.WriteLine($"== {Path.GetFileName(args[a])}");
    foreach (string line in File.ReadLines(args[a]))
    {
        if (line.Length < 20 || line[0] == '#' || line[0] == '﻿') continue;
        string[] parts = line.Split(' ', 4);
        uint t = (uint)TimeSpan.ParseExact(parts[0], @"hh\:mm\:ss\.fff", CultureInfo.InvariantCulture).TotalMilliseconds;
        byte[] data = Convert.FromHexString(parts[2]);

        // run the frames between packets, 16 ms apart
        for (; clock + 16 < t; clock += 16) { Time.Ticks = clock; tracker.Update(); }
        clock = Math.Max(clock, t);
        Time.Ticks = clock;

        // the recorder only kept sounds near the player, so stand the player on them
        if (data[0] == 0x54) { player.X = (ushort)(data[6] << 8 | data[7]); player.Y = (ushort)(data[8] << 8 | data[9]); }

        tracker.OnPacket(data);
    }
}
for (uint end = clock + 200_000; clock < end; clock += 16) { Time.Ticks = clock; tracker.Update(); }
