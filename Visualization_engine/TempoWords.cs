using System.Text.RegularExpressions;

namespace SynthesiaClone;

/// <summary>A printed word that names a tempo the song already had.</summary>
public enum ReturnWord
{
    /// <summary>"Tempo I", "Tempo primo", "come prima": the song's first tempo.</summary>
    FirstTempo,

    /// <summary>"a tempo": the tempo before the last change away from it.</summary>
    ATempo
}

/// <summary>
/// Return words in the TEMPO panel (Phase 4 of the per-song tempo plan). Phase 4 found the reader
/// misses too many of them, mostly those printed below the staff, for them to play by default, so
/// the panel only shows the tempo one names and offers USE. Words such as "Andante" fix no tempo
/// and stay hints. <see cref="Kind"/> follows <c>Research/omr/tempo_words.py</c>'s <c>return_kind</c>.
/// </summary>
public static partial class TempoWords
{
    // OCR reads the roman one as I, l or 1, and the degree sign as °, º or o.
    [GeneratedRegex(@"\btempo\s*(?:i|l|1|primo|io|1o)(?![a-z])\s*[°º.]?|(?<![a-z])(?:1|i)\s*[°º]\s*tempo\b|\bcome\s+prima\b",
        RegexOptions.IgnoreCase)]
    private static partial Regex FirstTempoPattern();

    [GeneratedRegex(@"(?<![a-z])a\s*tempo\b", RegexOptions.IgnoreCase)]
    private static partial Regex ATempoPattern();

    // A tempo word after the return word changes it ("a tempo, più lento"), so it no longer names one.
    [GeneratedRegex(@"più|piu|meno|mosso|animato|calmando|lento|lent\b|vite|plus|moins|rit|rall|allarg|accel|string|" +
        @"langsam|schnell|bewegt|ruhig|slower|faster", RegexOptions.IgnoreCase)]
    private static partial Regex ModifierPattern();

    public static ReturnWord? Kind(string? text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return null;
        }
        foreach ((ReturnWord kind, Regex pattern) in new[]
                 {
                     (ReturnWord.FirstTempo, FirstTempoPattern()), (ReturnWord.ATempo, ATempoPattern())
                 })
        {
            Match match = pattern.Match(text);
            if (match.Success)
            {
                return ModifierPattern().IsMatch(text[(match.Index + match.Length)..]) ? null : kind;
            }
        }
        return null;
    }

    /// <summary>
    /// The tempo a return word at <paramref name="measure"/> names in <paramref name="map"/>, or null
    /// when the map has none to go back to. "a tempo" goes back past the latest change before it;
    /// changes at <paramref name="returnBars"/>, where other return words are printed, are returns
    /// themselves and are not what it goes back past.
    /// </summary>
    public static TempoMark? Resolve(SongTempoMap map, int measure, ReturnWord kind, IReadOnlyCollection<int> returnBars)
    {
        ArgumentNullException.ThrowIfNull(map);
        ArgumentNullException.ThrowIfNull(returnBars);
        if (measure <= 0)
        {
            return null;
        }
        if (kind == ReturnWord.FirstTempo)
        {
            return map.Start;
        }
        List<BarTempo> ordered = map.Changes.OrderBy(static change => change.Measure)
            .ThenBy(static change => change.Offset).ToList();
        int away = ordered.FindLastIndex(change => change.Measure < measure && !returnBars.Contains(change.Measure));
        if (away < 0)
        {
            return null;
        }
        return away == 0 ? map.Start : ordered[away - 1].Tempo;
    }

    /// <summary>The measures where the listed marks print a return word.</summary>
    public static IReadOnlySet<int> ReturnBars(IEnumerable<PrintedMark> marks) =>
        marks.Where(static mark => mark.Measure is not null && Kind(mark.Source.Text) is not null)
            .Select(static mark => mark.Measure!.Value).ToHashSet();

    /// <summary>
    /// A return word printed without a number, taken as the tempo it names in <paramref name="map"/>,
    /// so USE can take it in like a printed number; null for any other mark, or when it names none.
    /// </summary>
    public static PrintedMark? Named(PrintedMark mark, SongTempoMap map, IReadOnlyCollection<int> returnBars) =>
        mark.Tempo is null && mark.Source.Bpm is null && mark.Measure is int measure &&
        Kind(mark.Source.Text) is ReturnWord kind && Resolve(map, measure, kind, returnBars) is TempoMark tempo
            ? mark with { Tempo = tempo }
            : null;
}
