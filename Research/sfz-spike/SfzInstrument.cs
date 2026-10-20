using System.Globalization;
using System.Text.RegularExpressions;

namespace SfzSpike;

/// <summary>One playable SFZ region, with its group's opcodes folded in.</summary>
public sealed record SfzRegion(
    string Sample,
    int LoKey,
    int HiKey,
    int LoVel,
    int HiVel,
    int PitchKeycenter,
    double PitchKeytrack,
    double Tune,
    double VolumeDb,
    double AmpVeltrack,
    double AmpegRelease,
    bool ReleaseTrigger,
    double RtDecay,
    int Group,
    int OffBy,
    double LoRand,
    double HiRand,
    int OnLoCc64,
    int OnHiCc64)
{
    /// <summary>Started by the sustain pedal entering a range rather than by a key.</summary>
    public bool PedalTriggered => OnLoCc64 >= 0 && OnHiCc64 >= 0;
}

/// <summary>
/// The subset of SFZ the Salamander piano uses: &lt;control&gt;, &lt;global&gt;, &lt;group&gt; and
/// &lt;region&gt; headers and the opcodes in <see cref="Supported"/>. Anything else is counted,
/// so coverage is a measured number rather than a claim.
/// </summary>
public sealed class SfzInstrument
{
    public static readonly IReadOnlySet<string> Supported = new HashSet<string>(StringComparer.Ordinal)
    {
        "sample", "key", "lokey", "hikey", "lovel", "hivel", "pitch_keycenter", "pitch_keytrack", "tune",
        "volume", "amp_veltrack", "ampeg_release", "trigger", "rt_decay", "group", "off_by", "lorand",
        "hirand", "on_locc64", "on_hicc64", "default_path"
    };

    private static readonly Regex Token = new(@"<(\w+)>|([A-Za-z0-9_]+)=", RegexOptions.Compiled);

    public SfzInstrument(string path)
    {
        Path = System.IO.Path.GetFullPath(path);
        Directory = System.IO.Path.GetDirectoryName(Path)!;
        List<SfzRegion> regions = [];
        Dictionary<string, string> control = [];
        Dictionary<string, string> global = [];
        Dictionary<string, string> group = [];
        Dictionary<string, string>? region = null;
        string header = "";

        void Close()
        {
            if (region is not null)
            {
                regions.Add(Build(region, control.GetValueOrDefault("default_path", "")));
            }
            region = null;
        }

        foreach (string rawLine in File.ReadLines(Path))
        {
            int comment = rawLine.IndexOf("//", StringComparison.Ordinal);
            string line = comment >= 0 ? rawLine[..comment] : rawLine;
            MatchCollection matches = Token.Matches(line);
            for (int index = 0; index < matches.Count; index++)
            {
                Match match = matches[index];
                if (match.Groups[1].Success)
                {
                    Close();
                    header = match.Groups[1].Value;
                    switch (header)
                    {
                        case "control":
                            control = [];
                            break;
                        case "global":
                            global = [];
                            group = [];
                            break;
                        case "group":
                            group = new Dictionary<string, string>(global);
                            break;
                        case "region":
                            region = new Dictionary<string, string>(group);
                            break;
                        default:
                            UnknownHeaders[header] = UnknownHeaders.GetValueOrDefault(header) + 1;
                            break;
                    }
                    continue;
                }
                int valueStart = match.Index + match.Length;
                int valueEnd = index + 1 < matches.Count ? matches[index + 1].Index : line.Length;
                string key = match.Groups[2].Value;
                string value = line[valueStart..valueEnd].Trim();
                Opcodes[key] = Opcodes.GetValueOrDefault(key) + 1;
                Dictionary<string, string> target = header switch
                {
                    "control" => control,
                    "global" => global,
                    "group" => group,
                    _ => region ?? group
                };
                target[key] = value;
            }
        }
        Close();
        Regions = regions;
    }

    public string Path { get; }
    public string Directory { get; }
    public IReadOnlyList<SfzRegion> Regions { get; }

    /// <summary>Every opcode met, with how many times; <see cref="Supported"/> says which are played.</summary>
    public Dictionary<string, int> Opcodes { get; } = new(StringComparer.Ordinal);
    public Dictionary<string, int> UnknownHeaders { get; } = new(StringComparer.Ordinal);

    public IEnumerable<string> SamplePaths => Regions.Select(region => region.Sample).Distinct(StringComparer.OrdinalIgnoreCase);

    public string ResolveSample(string sample) =>
        System.IO.Path.GetFullPath(System.IO.Path.Combine(Directory, sample.Replace('\\', System.IO.Path.DirectorySeparatorChar)));

    private static SfzRegion Build(Dictionary<string, string> opcodes, string defaultPath)
    {
        int Key(string name, int fallback) => opcodes.TryGetValue(name, out string? value) ? ParseKey(value) : fallback;
        double Number(string name, double fallback) => opcodes.TryGetValue(name, out string? value)
            ? double.Parse(value, CultureInfo.InvariantCulture)
            : fallback;
        int Integer(string name, int fallback) => (int)Math.Round(Number(name, fallback));

        int key = Key("key", -2);
        int loKey = key != -2 ? key : Key("lokey", 0);
        int hiKey = key != -2 ? key : Key("hikey", 127);
        return new SfzRegion(
            Sample: defaultPath + (opcodes.GetValueOrDefault("sample") ?? throw new InvalidDataException("A region has no sample.")),
            LoKey: loKey,
            HiKey: hiKey,
            LoVel: Integer("lovel", 0),
            HiVel: Integer("hivel", 127),
            PitchKeycenter: key != -2 ? key : Key("pitch_keycenter", 60),
            PitchKeytrack: Number("pitch_keytrack", 100),
            Tune: Number("tune", 0),
            VolumeDb: Number("volume", 0),
            AmpVeltrack: Number("amp_veltrack", 100),
            AmpegRelease: Number("ampeg_release", 0.001),
            ReleaseTrigger: opcodes.GetValueOrDefault("trigger") == "release",
            RtDecay: Number("rt_decay", 0),
            Group: Integer("group", 0),
            OffBy: Integer("off_by", 0),
            LoRand: Number("lorand", 0),
            HiRand: Number("hirand", 1),
            OnLoCc64: Integer("on_locc64", -1),
            OnHiCc64: Integer("on_hicc64", -1));
    }

    /// <summary>A MIDI key number, or a note name such as c#4 (C4 is 60, as SFZ counts).</summary>
    public static int ParseKey(string value)
    {
        if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int number))
        {
            return number;
        }
        Match note = Regex.Match(value.Trim().ToLowerInvariant(), @"^([a-g])([#b]?)(-?\d+)$");
        if (!note.Success)
        {
            throw new InvalidDataException($"'{value}' is not a key.");
        }
        int pitch = "c d ef g a b".IndexOf(note.Groups[1].Value[0]);
        pitch += note.Groups[2].Value == "#" ? 1 : note.Groups[2].Value == "b" ? -1 : 0;
        return pitch + 12 * (int.Parse(note.Groups[3].Value, CultureInfo.InvariantCulture) + 1);
    }
}
