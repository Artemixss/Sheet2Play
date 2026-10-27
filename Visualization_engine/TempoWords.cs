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
/// Tempo words printed without a number (Phase 4 of the per-song tempo plan). They play by default,
/// as the user chose on 2026-10-27 after trying them, although only relative words ("più mosso")
/// passed Phase 4's rule: absolute words ("Andante") are guesses that are often off for a given
/// piece, and the reader misses many return words ("a tempo"), so a relative passage may not end.
/// IGNORE stops any of them. <see cref="Kind"/> follows <c>Research/omr/tempo_words.py</c>'s
/// <c>return_kind</c>, the rest <c>tempo_word_corpus.py</c>.
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

    // The median quarter BPM printed with each word across all PDMX pairs (dev and held-out), the frozen
    // Phase 4 method rebuilt on twice the data once the held-out judgement was done
    // (Research/omr/reports/song-tempo/phase4/word-survey.json, table_v2). Composer cross-validation found
    // it about twice as close as 120 and no worse than textbook ranges, clamping or a table per meter; one
    // score in six is still more than 40% off, so IGNORE matters. test_tempo_word_corpus.py checks these.
    private static readonly Dictionary<string, double> AbsoluteQuarterBpm = new()
    {
        ["adagio"] = 69.0, ["allegretto"] = 112.0, ["allegro"] = 132.0, ["allegro moderato"] = 96.0,
        ["andante"] = 80.0, ["andante con moto"] = 86.0, ["andantino"] = 78.0, ["fast"] = 171.0, ["grave"] = 69.0,
        ["langsam"] = 61.0, ["larghetto"] = 64.0, ["largo"] = 50.0, ["lent"] = 57.0, ["lento"] = 66.0,
        ["moderately"] = 108.5, ["moderato"] = 100.0, ["mässig"] = 63.0, ["prestissimo"] = 232.0, ["presto"] = 184.0,
        ["slow"] = 75.0, ["slowly"] = 84.0, ["vivace"] = 160.0
    };

    // The median factor on the tempo printed before, from the same pairs; it passed the held-out rule.
    public const double FasterFactor = 1.137;
    public const double SlowerFactor = 0.898;

    private static readonly string[] AbsoluteWords =
    [
        "prestissimo", "presto", "vivacissimo", "vivace", "vivo", "allegrissimo", "allegretto", "allegro",
        "moderato", "andantino", "andante", "adagietto", "adagio", "larghetto", "largo", "lento", "grave",
        "slowly", "slow", "moderately", "moderate", "fast", "quickly", "lively", "langsam", "mässig", "massig",
        "lebhaft", "schnell", "lent", "modéré", "modere", "vif"
    ];

    private static readonly string[] FasterWords =
    [
        "più mosso", "piu mosso", "più animato", "piu animato", "animato", "più allegro", "piu allegro",
        "faster", "plus vite", "schneller", "doppio movimento"
    ];

    private static readonly string[] SlowerWords =
    [
        "meno mosso", "più lento", "piu lento", "meno", "slower", "moins vite", "langsamer", "calmando",
        "più tranquillo", "piu tranquillo"
    ];

    [GeneratedRegex(@"[-♩-♬]")]
    private static partial Regex GlyphPattern();

    [GeneratedRegex(@"[()\[\]=,.:;!""'*\d]|\bc\.|\bca\.|\bcirca\b|\bbpm\b")]
    private static partial Regex NoisePattern();

    [GeneratedRegex(@"[a-zà-üß]+")]
    private static partial Regex WordPattern();

    /// <summary>Lower case, without the number, the note glyphs, brackets and punctuation, as the research counted words.</summary>
    public static string Normalized(string text)
    {
        string plain = NoisePattern().Replace(GlyphPattern().Replace(text, " ").ToLowerInvariant(), " ");
        return string.Join(' ', plain.Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private static bool Contains(string words, string phrase) =>
        Regex.IsMatch(words, $@"(?<![a-zà-ü]){Regex.Escape(phrase)}(?![a-zà-ü])");

    /// <summary>The factor a relative word ("più mosso", "slower") puts on the tempo before it, or null.</summary>
    public static double? RelativeFactor(string words) =>
        FasterWords.Any(phrase => Contains(words, phrase)) ? FasterFactor
        : SlowerWords.Any(phrase => Contains(words, phrase)) ? SlowerFactor
        : null;

    /// <summary>The quarter BPM the table guesses for an absolute word: its own entry, else its first tempo word's.</summary>
    public static double? AbsoluteGuess(string words)
    {
        if (RelativeFactor(words) is not null || Contains(words, "a tempo"))
        {
            return null;
        }
        if (AbsoluteQuarterBpm.TryGetValue(words, out double bpm))
        {
            return bpm;
        }
        string? head = WordPattern().Matches(words).Select(static match => match.Value)
            .FirstOrDefault(word => AbsoluteWords.Contains(word));
        return head is not null && AbsoluteQuarterBpm.TryGetValue(head, out double headBpm) ? headBpm : null;
    }

    /// <summary>
    /// A tempo word printed without a number, with the tempo the table guesses for it in <paramref name="map"/>:
    /// an absolute word its table tempo, a relative word its factor on the tempo before its bar. Null for a
    /// return word, a number, or a word the table has nothing for.
    /// </summary>
    public static PrintedMark? Guessed(PrintedMark mark, SongTempoMap map)
    {
        if (mark.Tempo is not null || mark.Source.Bpm is not null || mark.Measure is not int measure ||
            Kind(mark.Source.Text) is not null)
        {
            return null;
        }
        string words = Normalized(mark.Source.Text);
        TempoMark? tempo = null;
        if (RelativeFactor(words) is double factor)
        {
            if (measure > 0)
            {
                TempoMark before = SongTempoMaps.TempoAt(map, measure - 1);
                tempo = new TempoMark(Math.Round(before.Bpm * factor), before.Unit);
            }
        }
        else if (AbsoluteGuess(words) is double bpm)
        {
            // Half to even, as the research scored the guesses.
            tempo = new TempoMark(Math.Round(bpm), BeatUnit.Quarter);
        }
        return tempo is not null && TempoRules.IsInRange(tempo.Bpm) ? mark with { Tempo = tempo } : null;
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
