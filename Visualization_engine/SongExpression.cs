namespace SynthesiaClone;

/// <summary>What the EXPRESSION panel turns on. Tempo marks always play.</summary>
/// <param name="Pedal">Sustain pedal from the score's pedal marks, or from a MIDI file's CC64.</param>
/// <param name="Dynamics">Velocities from dynamic marks and hairpins; otherwise every note at mf (80).</param>
/// <param name="Articulations">Staccato and its relatives shorten, accents strike harder, marked chords
/// roll, and grace notes play.</param>
/// <param name="Repeats">Walk the score's repeats and voltas; otherwise every measure once, in order.</param>
public sealed record ExpressionOptions(
    bool Pedal = true,
    bool Dynamics = true,
    bool Articulations = true,
    bool Repeats = true)
{
    /// <summary>No expression, repeats played: exactly what the app played before expression existed.</summary>
    public static ExpressionOptions None { get; } = new(Pedal: false, Dynamics: false, Articulations: false);
}

/// <summary>Which expression a song has anything for, so the panel can say when a switch does nothing.</summary>
public sealed record ExpressionAvailability(bool Pedal, bool Dynamics, bool Articulations, bool Repeats)
{
    public static ExpressionAvailability Nothing { get; } = new(false, false, false, false);
}

/// <summary>A sustain pedal change: MIDI CC64, 0 (up) to 127 (down), at a song time in seconds.</summary>
public readonly record struct PedalChange(double Time, int Value)
{
    public bool IsDown => Value >= 64;
}

/// <summary>The notes and pedal a song plays under one set of expression choices.</summary>
public sealed record SongPlayback(List<Note> Notes, IReadOnlyList<PedalChange> Pedal);

/// <summary>The playing rules for a performance's marks. <see cref="SongTimeline"/> applies them.</summary>
/// <remarks>
/// Velocities follow MuseScore's for the same marks, so a score sounds about as loud here as in
/// the program most of these files come from. Articulation lengths are the usual textbook
/// proportions. Grace notes are placed before the beat rather than on it, so the note they
/// decorate still falls with the other hand.
/// </remarks>
public static class SongExpression
{
    public const int DefaultVelocity = 80;

    /// <summary>A crescendo or diminuendo with no dynamic at its end moves this far.</summary>
    public const int HairpinStep = 16;

    /// <summary>How far past a hairpin's end the dynamic it leads to may sit, in quarter notes.</summary>
    private const double HairpinReachBeats = 1.0;

    /// <summary>The gap between the notes of a rolled chord.</summary>
    public const double RollStepSeconds = 0.03;

    /// <summary>Grace note lengths, in quarter notes: a slashed one is a 32nd, an unslashed one a 16th.</summary>
    public const double SlashedGraceBeats = 0.125;
    public const double GraceBeats = 0.25;

    /// <summary>A shortened note still sounds at least this long, unless it was written shorter.</summary>
    private const double MinimumSoundingSeconds = 0.04;

    private const double Epsilon = 1e-6;
    private const double AttackTolerance = 1e-3;

    private static readonly Dictionary<string, int> Levels = new(StringComparer.Ordinal)
    {
        ["pppppp"] = 1, ["ppppp"] = 5, ["pppp"] = 10, ["ppp"] = 16, ["pp"] = 33, ["p"] = 49,
        ["mp"] = 64, ["mf"] = 80, ["f"] = 96, ["ff"] = 112, ["fff"] = 126,
        ["ffff"] = 127, ["fffff"] = 127, ["ffffff"] = 127
    };

    /// <summary>Marks that strike one chord: the attack, and the level after it when it changes.</summary>
    private static readonly Dictionary<string, (int Attack, int? After)> Attacks = new(StringComparer.Ordinal)
    {
        ["sf"] = (112, null), ["sfz"] = (112, null), ["fz"] = (112, null), ["rf"] = (112, null),
        ["rfz"] = (112, null), ["sff"] = (126, null), ["sffz"] = (126, null),
        ["fp"] = (96, 49), ["sfp"] = (112, 49), ["sfzp"] = (112, 49), ["sfpp"] = (112, 33)
    };

    public static ExpressionAvailability Availability(SongPerformance performance)
    {
        bool articulations = performance.Notes.Any(static note =>
            note.Grace || LengthFactor(note.Articulations) != 1.0 || AccentBoost(note.Articulations) != 0 ||
            note.Articulations.Contains("arpeggiate"));
        bool repeats = performance.PlayOrder.Count != performance.Measures.Count ||
            performance.PlayOrder.Where(static (measure, index) => measure != index).Any();
        return new ExpressionAvailability(
            Pedal: performance.Pedals.Any(static pedal => PedalValues(pedal).Length > 0),
            Dynamics: performance.Wedges.Count > 0 || performance.Dynamics.Any(static mark => Resolve(mark) is not (null, null)),
            Articulations: articulations,
            Repeats: repeats);
    }

    // --- Articulations --------------------------------------------------------------------------

    /// <summary>The part of a note's written length that sounds.</summary>
    public static double LengthFactor(IReadOnlyList<string> marks)
    {
        bool staccato = marks.Contains("staccato");
        bool tenuto = marks.Contains("tenuto");
        if (marks.Contains("staccatissimo") || marks.Contains("spiccato"))
        {
            return 0.25;
        }
        if (marks.Contains("detached-legato") || (staccato && tenuto))
        {
            return 0.75;
        }
        return staccato ? 0.5 : 1.0;
    }

    public static int AccentBoost(IReadOnlyList<string> marks) =>
        marks.Contains("strong-accent") ? 24 : marks.Contains("accent") ? 16 : 0;

    /// <summary>The end of a note shortened by its articulation, never below a short audible floor.</summary>
    internal static double SoundingEnd(double start, double writtenEnd, double shortenedEnd) =>
        shortenedEnd >= writtenEnd ? writtenEnd : Math.Max(shortenedEnd, Math.Min(writtenEnd, start + MinimumSoundingSeconds));

    /// <summary>Rolls each marked chord upward, every note ending where it was written to end.</summary>
    internal static void Roll(List<PlacedNote> placed)
    {
        foreach (IGrouping<(int, int, double), PlacedNote> chord in placed
                     .Where(static note => note.Rolled)
                     .GroupBy(static note => (note.Occurrence, note.Part, note.StartBeat))
                     .ToList())
        {
            List<PlacedNote> notes = chord.OrderBy(static note => note.KeyIndex).ToList();
            if (notes.Count < 2)
            {
                continue;
            }
            double shortest = notes.Min(static note => note.End - note.Start);
            double step = Math.Min(RollStepSeconds, shortest * 0.5 / (notes.Count - 1));
            for (int index = 1; index < notes.Count; index++)
            {
                notes[index].Start += index * step;
            }
        }
    }

    /// <summary>
    /// Grace notes in written order, each group ending on the beat of the note it decorates.
    /// </summary>
    /// <param name="graces">Grace notes of one occurrence of a measure, in score order.</param>
    internal static IEnumerable<(SongNote Note, double StartBeat, double EndBeat)> PlaceGraces(
        IEnumerable<SongNote> graces, double measureStart, double songStart)
    {
        foreach (IGrouping<(int, int, string, double), SongNote> group in graces
                     .GroupBy(static note => (note.Part, note.Staff, note.Voice, note.Offset)))
        {
            List<SongNote> notes = group.ToList();
            double beat = measureStart + group.Key.Item4;
            double total = notes.Sum(static note => note.GraceSlash ? SlashedGraceBeats : GraceBeats);
            double scale = beat - total >= songStart ? 1.0 : Math.Max(0, beat - songStart) / total;
            if (total * scale < Epsilon)
            {
                continue;
            }
            double position = beat - total * scale;
            foreach (SongNote note in notes)
            {
                double length = (note.GraceSlash ? SlashedGraceBeats : GraceBeats) * scale;
                yield return (note, position, position + length);
                position += length;
            }
        }
    }

    // --- Pedal ----------------------------------------------------------------------------------

    /// <summary>The CC64 values one pedal mark asks for, in order.</summary>
    public static int[] PedalValues(SongPedal pedal)
    {
        if (pedal.Source == "mark")
        {
            return pedal.Type switch
            {
                "start" or "resume" => [127],
                "stop" or "discontinue" => [0],
                "change" => [0, 127],
                _ => []
            };
        }
        if (pedal.Source == "sound" && pedal.Type == "damper" && pedal.SoundValue is string value)
        {
            if (value == "yes")
            {
                return [127];
            }
            if (value == "no")
            {
                return [0];
            }
            if (double.TryParse(value, System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out double percent) && double.IsFinite(percent))
            {
                return [(int)Math.Round(Math.Clamp(percent, 0, 100) * 1.27)];
            }
        }
        return [];
    }

    /// <summary>
    /// Pedal changes in song seconds. Every part's marks drive the one pedal, because every part
    /// plays through one piano.
    /// </summary>
    internal static IReadOnlyList<PedalChange> Pedal(SongPerformance performance, IReadOnlyList<int> order,
        double[] starts, Func<double, double> seconds)
    {
        Dictionary<int, List<SongPedal>> byMeasure = performance.Pedals
            .GroupBy(static pedal => pedal.Measure)
            .ToDictionary(static group => group.Key, static group => group.ToList());
        List<(double Beat, int Value)> marks = [];
        for (int occurrence = 0; occurrence < order.Count; occurrence++)
        {
            if (!byMeasure.TryGetValue(order[occurrence], out List<SongPedal>? pedals))
            {
                continue;
            }
            foreach (SongPedal pedal in pedals)
            {
                foreach (int value in PedalValues(pedal))
                {
                    marks.Add((starts[occurrence] + pedal.Offset, value));
                }
            }
        }
        // At one position a release goes before a press, so a stop and a start written in either
        // order make a pedal change rather than leaving the pedal up.
        List<(double Beat, int Value)> ordered = marks
            .Select(static (mark, index) => (mark, index))
            .OrderBy(static item => item.mark.Beat)
            .ThenBy(static item => item.mark.Value >= 64 ? 1 : 0)
            .ThenBy(static item => item.index)
            .Select(static item => item.mark)
            .ToList();
        List<PedalChange> changes = [];
        int state = 0;
        foreach ((double beat, int value) in ordered)
        {
            if (value == state)
            {
                continue;
            }
            changes.Add(new PedalChange(Math.Max(0, seconds(beat)), value));
            state = value;
        }
        return changes;
    }

    // --- Dynamics -------------------------------------------------------------------------------

    /// <summary>A dynamic as a level it sets and an attack it gives the notes at its position.</summary>
    internal static (int? Level, int? Attack) Resolve(SongDynamic mark)
    {
        int? sound = mark.SoundDynamics is double percent && double.IsFinite(percent)
            ? Math.Clamp((int)Math.Round(percent * 0.9), 1, 127)
            : null;
        int? level = null;
        int? attack = null;
        bool known = false;
        foreach (string name in (mark.Mark ?? "").Split('+', StringSplitOptions.RemoveEmptyEntries))
        {
            if (Levels.TryGetValue(name, out int value))
            {
                level = value;
                known = true;
            }
            else if (Attacks.TryGetValue(name, out (int Attack, int? After) strike))
            {
                attack = strike.Attack;
                level = strike.After ?? level;
                known = true;
            }
        }
        // MusicXML's <sound dynamics> is the exporter's own playback value: the level of a plain
        // dynamic, the attack of a sforzando.
        if (sound is int exported)
        {
            if (attack is not null)
            {
                attack = exported;
            }
            else if (level is not null || !known)
            {
                level = exported;
            }
        }
        return (level, attack);
    }

    internal static DynamicsMap Dynamics(SongPerformance performance, IReadOnlyList<int> order, double[] starts)
    {
        DynamicsMap map = new();
        Dictionary<int, List<SongDynamic>> byMeasure = performance.Dynamics
            .GroupBy(static mark => mark.Measure)
            .ToDictionary(static group => group.Key, static group => group.ToList());
        for (int occurrence = 0; occurrence < order.Count; occurrence++)
        {
            if (!byMeasure.TryGetValue(order[occurrence], out List<SongDynamic>? marks))
            {
                continue;
            }
            foreach (SongDynamic mark in marks)
            {
                (int? level, int? attack) = Resolve(mark);
                double beat = starts[occurrence] + mark.Offset;
                if (attack is int strike)
                {
                    map.Part(mark.Part).Attacks.Add((beat, strike));
                }
                if (level is int value)
                {
                    map.Part(mark.Part).AddLevel(beat, value, fromMark: true);
                }
            }
        }

        // Hairpins in the order they start, so one that follows another starts where it ended.
        List<(int Part, string Kind, double Start, double End)> spans = [];
        foreach (SongWedge wedge in performance.Wedges)
        {
            for (int occurrence = 0; occurrence < order.Count; occurrence++)
            {
                if (order[occurrence] != wedge.StartMeasure)
                {
                    continue;
                }
                int end = occurrence;
                while (end < order.Count && order[end] != wedge.EndMeasure)
                {
                    end++;
                }
                if (end == order.Count)
                {
                    continue;
                }
                double startBeat = starts[occurrence] + wedge.StartOffset;
                double endBeat = starts[end] + wedge.EndOffset;
                if (endBeat > startBeat + Epsilon)
                {
                    spans.Add((wedge.Part, wedge.Kind, startBeat, endBeat));
                }
            }
        }
        foreach ((int part, string kind, double start, double end) in spans.OrderBy(static span => span.Start))
        {
            DynamicsMap.PartDynamics dynamics = map.Part(part);
            int from = dynamics.LevelAt(start).Level;
            bool rising = kind == "crescendo";
            int? next = dynamics.NextMarkLevel(start, end + HairpinReachBeats);
            int target = next is int mark && (rising ? mark > from : mark < from)
                ? mark
                : Math.Clamp(from + (rising ? HairpinStep : -HairpinStep), 1, 127);
            dynamics.Spans.Add((start, end, from, target));
            dynamics.AddLevel(end, target, fromMark: false);
        }
        return map;
    }

    /// <summary>Velocity by part and position, from dynamics, attacks and hairpins.</summary>
    internal sealed class DynamicsMap
    {
        private readonly Dictionary<int, PartDynamics> parts = [];

        internal PartDynamics Part(int part)
        {
            if (!parts.TryGetValue(part, out PartDynamics? dynamics))
            {
                dynamics = new PartDynamics();
                parts[part] = dynamics;
            }
            return dynamics;
        }

        public int VelocityAt(int part, double beat) =>
            parts.TryGetValue(part, out PartDynamics? dynamics) ? dynamics.VelocityAt(beat) : DefaultVelocity;

        internal sealed class PartDynamics
        {
            // Sorted by position; at one position a hairpin's own end level goes before a written mark.
            private readonly List<(double Beat, bool FromMark, int Level)> levels = [];
            public List<(double Beat, int Velocity)> Attacks { get; } = [];
            public List<(double Start, double End, int From, int To)> Spans { get; } = [];

            public void AddLevel(double beat, int level, bool fromMark)
            {
                int index = 0;
                while (index < levels.Count &&
                       (levels[index].Beat < beat - Epsilon ||
                        (Math.Abs(levels[index].Beat - beat) <= Epsilon && (fromMark || !levels[index].FromMark))))
                {
                    index++;
                }
                levels.Insert(index, (beat, fromMark, level));
            }

            public (int Level, double Beat) LevelAt(double beat)
            {
                (int Level, double Beat) found = (DefaultVelocity, double.NegativeInfinity);
                foreach ((double at, _, int level) in levels)
                {
                    if (at > beat + Epsilon)
                    {
                        break;
                    }
                    found = (level, at);
                }
                return found;
            }

            public int? NextMarkLevel(double after, double until)
            {
                foreach ((double at, bool fromMark, int level) in levels)
                {
                    if (fromMark && at > after + Epsilon && at <= until + Epsilon)
                    {
                        return level;
                    }
                }
                return null;
            }

            public int VelocityAt(double beat)
            {
                int attack = 0;
                foreach ((double at, int velocity) in Attacks)
                {
                    if (Math.Abs(at - beat) <= AttackTolerance)
                    {
                        attack = Math.Max(attack, velocity);
                    }
                }
                if (attack > 0)
                {
                    return attack;
                }
                (int level, double levelBeat) = LevelAt(beat);
                for (int index = Spans.Count - 1; index >= 0; index--)
                {
                    (double start, double end, int from, int to) = Spans[index];
                    if (start <= beat + Epsilon && beat < end - Epsilon && start >= levelBeat - Epsilon)
                    {
                        return (int)Math.Round(from + (to - from) * ((beat - start) / (end - start)));
                    }
                }
                return level;
            }
        }
    }

    /// <summary>A note between placing and becoming a <see cref="Note"/>.</summary>
    internal sealed class PlacedNote
    {
        public required int Occurrence { get; init; }
        public required int Part { get; init; }
        public required int KeyIndex { get; init; }
        public required double StartBeat { get; init; }
        public required double Start { get; set; }
        public required double End { get; init; }
        public required int Velocity { get; init; }
        public bool Rolled { get; init; }
    }
}

/// <summary>A loaded song as the player plays it under the EXPRESSION panel's choices.</summary>
public static class ExpressionPlayback
{
    public static SongPlayback ForSong(SongLoadResult song, ExpressionOptions expression)
    {
        ArgumentNullException.ThrowIfNull(song);
        ArgumentNullException.ThrowIfNull(expression);
        if (song.Performance is SongPerformance performance)
        {
            return SongTimeline.Build(performance, SongTimelineOptions.For(expression));
        }
        // A MIDI file already carries its own velocities, lengths and repeats; only its pedal is optional.
        return new SongPlayback(song.Notes, expression.Pedal && song.Pedal is not null ? song.Pedal : []);
    }

    public static ExpressionAvailability Availability(SongLoadResult song) =>
        song.Performance is SongPerformance performance
            ? SongExpression.Availability(performance)
            : ExpressionAvailability.Nothing with { Pedal = song.Pedal is { Count: > 0 } };

    /// <summary>Where a position under one set of choices is under another; only repeats move it.</summary>
    public static double MapPosition(SongLoadResult song, ExpressionOptions from, ExpressionOptions to, double seconds) =>
        song.Performance is SongPerformance performance && from.Repeats != to.Repeats
            ? SongTimeline.MapPosition(performance, SongTimelineOptions.For(from), SongTimelineOptions.For(to), seconds)
            : seconds;
}
