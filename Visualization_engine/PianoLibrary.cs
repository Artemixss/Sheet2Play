using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

/// <summary>
/// What an installed SFZ piano says about itself, from its <c>piano.json</c>.
/// </summary>
/// <param name="ShortName">The card title, for example "Salamander".</param>
/// <param name="Attribution">Shown in the app, because the sample licence (CC BY) requires it.</param>
public sealed record PianoDescription(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("short_name")] string ShortName,
    [property: JsonPropertyName("sfz")] string Sfz,
    [property: JsonPropertyName("attribution")] string Attribution);

/// <summary>What the app found for the SFZ piano, and what to tell the user if it found nothing.</summary>
public sealed record PianoStatus(string? Directory, PianoDescription? Description, long Bytes, string? Problem)
{
    public bool IsAvailable => Directory is not null && Description is not null && Problem is null;
}

/// <summary>
/// An installed SFZ piano, loaded: the parsed instrument and its memory-mapped sample bank. Read-only,
/// so the live engine and an exporter on another thread share one.
/// </summary>
public sealed class SfzPiano
{
    internal SfzPiano(string directory, PianoDescription description, SfzInstrument instrument, SfzBank bank, DateTime bankWritten)
    {
        Directory = directory;
        Description = description;
        Instrument = instrument;
        Bank = bank;
        BankWritten = bankWritten;
    }

    public string Directory { get; }
    public PianoDescription Description { get; }
    public SfzInstrument Instrument { get; }
    public SfzBank Bank { get; }
    internal DateTime BankWritten { get; }
}

/// <summary>
/// Finds and loads the SFZ piano that <c>scripts\install-piano.ps1</c> installs under
/// <c>%LOCALAPPDATA%\Sheet2Play\pianos</c>, outside <c>dist\</c>, which every publish wipes.
/// </summary>
/// <remarks>
/// A loaded piano is kept for the life of the process and never unmapped. An MP3 export can still be
/// reading the bank on its worker when the user switches piano, and unmapping it under the worker
/// would crash the app; the mapping costs address space and page cache, not commit charge. Switching
/// back reuses it, unless the installer has rebuilt the bank since.
/// </remarks>
public static class PianoLibrary
{
    public const string FolderName = "pianos";
    public const string DescriptionName = "piano.json";

    /// <summary>The first half second of every sample is read at load, so no first note waits on the disk.</summary>
    private const double PrefetchSeconds = 0.5;

    private static readonly object CacheGate = new();
    private static SfzPiano? cached;

    public static string Folder => Path.Combine(SongCache.ApplicationDirectory, FolderName);

    /// <summary>The first installed piano (by folder name) with a description, an instrument and a bank.</summary>
    /// <param name="folder">The pianos folder; <see cref="Folder"/> unless a test gives its own.</param>
    public static PianoStatus Resolve(string? folder = null)
    {
        folder ??= Folder;
        const string notInstalled = "Salamander is not installed. Run scripts\\install-piano.ps1, then pick it again.";
        if (!System.IO.Directory.Exists(folder))
        {
            return new PianoStatus(null, null, 0, notInstalled);
        }
        foreach (string directory in System.IO.Directory.EnumerateDirectories(folder).Order(StringComparer.OrdinalIgnoreCase))
        {
            string descriptionPath = Path.Combine(directory, DescriptionName);
            if (!File.Exists(descriptionPath))
            {
                continue;
            }
            PianoDescription? description;
            try
            {
                description = JsonSerializer.Deserialize<PianoDescription>(File.ReadAllText(descriptionPath));
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
            {
                return new PianoStatus(null, null, 0, $"Could not read {descriptionPath}: {error.Message}");
            }
            if (description is null || string.IsNullOrWhiteSpace(description.Sfz))
            {
                return new PianoStatus(null, null, 0, $"{descriptionPath} does not name an instrument.");
            }
            string bank = Path.Combine(directory, SfzBank.BankName);
            if (!File.Exists(Path.Combine(directory, description.Sfz)) || !File.Exists(bank) ||
                !File.Exists(Path.Combine(directory, SfzBank.IndexName)))
            {
                return new PianoStatus(null, description, 0,
                    $"{description.Name} is incomplete. Run scripts\\install-piano.ps1 again.");
            }
            return new PianoStatus(directory, description, new FileInfo(bank).Length, null);
        }
        return new PianoStatus(null, null, 0, notInstalled);
    }

    /// <summary>Loads the installed piano, reporting failure as a status rather than an exception.</summary>
    public static (SfzPiano? Piano, PianoStatus Status) Load(string? folder = null)
    {
        PianoStatus status = Resolve(folder);
        if (!status.IsAvailable)
        {
            return (null, status);
        }
        string directory = status.Directory!;
        PianoDescription description = status.Description!;
        try
        {
            DateTime written = File.GetLastWriteTimeUtc(Path.Combine(directory, SfzBank.BankName));
            lock (CacheGate)
            {
                if (cached is not null && string.Equals(cached.Directory, directory, StringComparison.OrdinalIgnoreCase) &&
                    cached.BankWritten == written)
                {
                    return (cached, status);
                }
                SfzInstrument instrument = new(Path.Combine(directory, description.Sfz));
                SfzBank bank = SfzBank.Open(directory, instrument);
                bank.Prefetch((int)(PrefetchSeconds * AudioOutput.SampleRate));
                cached = new SfzPiano(directory, description, instrument, bank, written);
                return (cached, status);
            }
        }
        catch (Exception error)
        {
            return (null, status with { Directory = null, Problem = $"Could not load {description.Name}: {error.Message}" });
        }
    }

    /// <summary>
    /// Converts an instrument's samples into the 16-bit bank beside it, for the installer
    /// (<c>--build-piano-bank</c>): the samples are read once here instead of at every start.
    /// </summary>
    public static BankIndex BuildBank(string sfzPath, string directory) => SfzBank.Build(new SfzInstrument(sfzPath), directory);
}
