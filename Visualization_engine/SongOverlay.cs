namespace SynthesiaClone;

/// <summary>One played bar: where it starts, its number in the score, and which time through it is.</summary>
/// <param name="Pass">1 on the first time through, 2 on the second, and so on.</param>
/// <param name="Passes">How many times the timeline plays this measure, so a bar that never repeats
/// is not labelled "1st time".</param>
/// <param name="Measure">The measure's index in the performance, which the TEMPO panel stores.</param>
public readonly record struct OverlayBar(double Seconds, string Number, int Pass, int Passes, int Measure);

/// <summary>
/// What the playback screen draws over the falling notes for one timeline: the bar lines with their
/// numbers, and when the sustain pedal is down.
/// </summary>
/// <remarks>
/// Built once per playback session, from the same timeline options and pedal the session plays, so
/// a bar line falls with the first note of its bar and the pedal lane lights with the pedal that is
/// heard. Songs without a score (MIDI files and legacy caches) have no bars, only their pedal.
/// </remarks>
public sealed class SongOverlay
{
    /// <summary>Pedal values at or above this hold the dampers off, as in General MIDI.</summary>
    public const int PedalDownValue = 64;

    public static readonly SongOverlay Empty = new([], []);

    private readonly double[] barStarts;
    private readonly double[] pedalStarts;

    private SongOverlay(IReadOnlyList<OverlayBar> bars, IReadOnlyList<(double Start, double End)> pedalDown)
    {
        Bars = bars;
        PedalDown = pedalDown;
        barStarts = bars.Select(static bar => bar.Seconds).ToArray();
        pedalStarts = pedalDown.Select(static span => span.Start).ToArray();
    }

    /// <summary>Every played bar in time order.</summary>
    public IReadOnlyList<OverlayBar> Bars { get; }

    /// <summary>The spans during which the pedal is down, in time order and not overlapping.</summary>
    public IReadOnlyList<(double Start, double End)> PedalDown { get; }

    public static SongOverlay For(SongPerformance? performance, SongTimelineOptions options,
        IReadOnlyList<PedalChange> pedal)
    {
        ArgumentNullException.ThrowIfNull(options);
        ArgumentNullException.ThrowIfNull(pedal);
        List<OverlayBar> bars = [];
        if (performance is not null)
        {
            var (times, _, _) = SongTimeline.BarTimes(performance, options);
            Dictionary<int, int> passes = times
                .GroupBy(static bar => bar.Measure)
                .ToDictionary(static group => group.Key, static group => group.Count());
            Dictionary<int, int> seen = [];
            foreach ((int measure, _, double seconds) in times)
            {
                int pass = seen.GetValueOrDefault(measure) + 1;
                seen[measure] = pass;
                bars.Add(new OverlayBar(seconds, SongTempoMaps.BarName(performance, measure), pass, passes[measure],
                    measure));
            }
        }
        return new SongOverlay(bars, PedalSpans(pedal));
    }

    /// <summary>The bar playing at <paramref name="seconds"/>, or -1 before the first.</summary>
    public int BarIndexAt(double seconds) => LastAtOrBefore(barStarts, seconds);

    /// <summary>"Bar 12", or "Bar 12 · 2nd time" for a bar the timeline plays more than once; null with no bars.</summary>
    public string? BarLabel(double seconds)
    {
        if (Bars.Count == 0)
        {
            return null;
        }
        OverlayBar bar = Bars[Math.Max(0, BarIndexAt(seconds))];
        return bar.Passes > 1 ? $"Bar {bar.Number} · {Ordinal(bar.Pass)} time" : $"Bar {bar.Number}";
    }

    /// <summary>The first bar starting at or after <paramref name="seconds"/>; Bars.Count when there is none.</summary>
    public int FirstBarFrom(double seconds)
    {
        int index = Array.BinarySearch(barStarts, seconds);
        if (index < 0)
        {
            return ~index;
        }
        // Several bars cannot share a start, but walk back in case a zero-length one does.
        while (index > 0 && barStarts[index - 1] == seconds)
        {
            index--;
        }
        return index;
    }

    /// <summary>The first pedal span that has not ended by <paramref name="seconds"/>; PedalDown.Count when none.</summary>
    public int FirstPedalFrom(double seconds)
    {
        int index = Math.Max(0, LastAtOrBefore(pedalStarts, seconds));
        while (index < PedalDown.Count && PedalDown[index].End <= seconds)
        {
            index++;
        }
        return index;
    }

    public bool IsPedalDown(double seconds)
    {
        int index = LastAtOrBefore(pedalStarts, seconds);
        return index >= 0 && seconds < PedalDown[index].End;
    }

    private static int LastAtOrBefore(double[] starts, double seconds)
    {
        int index = Array.BinarySearch(starts, seconds);
        if (index >= 0)
        {
            while (index + 1 < starts.Length && starts[index + 1] == seconds)
            {
                index++;
            }
            return index;
        }
        return ~index - 1;
    }

    /// <summary>
    /// Pairs each press with the next release. A press while already down extends the span, and a
    /// pedal still down at the end stays down for good, which the lane draws as running off the top.
    /// </summary>
    private static List<(double Start, double End)> PedalSpans(IReadOnlyList<PedalChange> pedal)
    {
        List<(double, double)> spans = [];
        double? downSince = null;
        foreach (PedalChange change in pedal.OrderBy(static change => change.Time))
        {
            bool down = change.Value >= PedalDownValue;
            if (down && downSince is null)
            {
                downSince = change.Time;
            }
            else if (!down && downSince is double start)
            {
                if (change.Time > start)
                {
                    spans.Add((start, change.Time));
                }
                downSince = null;
            }
        }
        if (downSince is double open)
        {
            spans.Add((open, double.PositiveInfinity));
        }
        return spans;
    }

    private static string Ordinal(int number) => (number % 100) switch
    {
        11 or 12 or 13 => $"{number}th",
        _ => (number % 10) switch
        {
            1 => $"{number}st",
            2 => $"{number}nd",
            3 => $"{number}rd",
            _ => $"{number}th"
        }
    };
}
