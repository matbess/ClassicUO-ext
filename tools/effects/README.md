# Effect recorder tools

Used to build the buff tracker (`src/ClassicUO.Client/Game/Managers/BuffTracker.cs`). UOSA sends no buff packets
(0xDF), so the tracker works buffs and debuffs out from stat changes, flags, light, body, spell sounds and effects,
words and system messages. The client's effect recorder (profile key `record_effects`, Options > Experimental)
logs those packets to `Logs/Effects/*.log`; these tools read the logs.

- `decode.py LOG...`: print a recorder log as readable lines.
- `tracker-replay/`: replays recorder logs through the real BuffTracker source (linked from `src/`) and prints every
  buff bar change, to check the tracker without the game:
  `~/.dotnet/dotnet run --project tracker-replay -- <player serial hex> <magery> <log>...`

The recorder can be dropped from the client once the user is happy with the tracker (it's the last of the feature
commits on `extensions`, so it can be reverted on its own).
