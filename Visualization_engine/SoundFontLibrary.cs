using MeltySynth;

namespace SynthesiaClone;

/// <summary>
/// What the app found to play with, and what to tell the user if it found nothing.
/// </summary>
public sealed record SoundFontStatus(string? Path, long Bytes, string? Problem)
{
    public bool IsAvailable => Path is not null && Problem is null;
    public string? Name => Path is null ? null : System.IO.Path.GetFileName(Path);
}

/// <summary>
/// Finds and loads the SoundFont the built-in synthesiser plays.
/// </summary>
/// <remarks>
/// A SoundFont is a runtime asset in the sense <c>CLAUDE.md</c> warns about: invisible to the
/// compiler, so a build succeeds while the app degrades. Two rules follow.
///
/// First, the filename is never hardcoded - the folder is globbed. <c>verify-release.ps1</c>
/// cross-checks C#-referenced runtime assets against a regex covering ttf, otf, py, ico and
/// ps1, so <c>sf2</c> is not matched and a literal filename in this file would silently escape
/// the release check. Globbing keeps the check honest by making the filename irrelevant.
///
/// Second, missing means visibly missing. The precedent here is the font loader, which falls
/// back to Raylib's default and looks wrong with no explanation; this returns a
/// <see cref="SoundFontStatus.Problem"/> for the UI to show and lets the caller fall back to
/// an external MIDI device rather than to silence.
/// </remarks>
public static class SoundFontLibrary
{
    public const string FolderName = "soundfonts";

    /// <summary>
    /// Where a SoundFont may live, in the order they win.
    /// </summary>
    /// <remarks>
    /// The per-user folder comes before the shipped one so a chosen font survives a release:
    /// <c>verify-release.ps1</c> wipes <c>dist\</c> on every publish, and anything under
    /// <c>%LOCALAPPDATA%\Sheet2Play</c> does not live there.
    /// </remarks>
    public static IEnumerable<string> SearchFolders()
    {
        yield return System.IO.Path.Combine(SongCache.ApplicationDirectory, FolderName);
        yield return System.IO.Path.Combine(AppContext.BaseDirectory, "assets", FolderName);
    }

    /// <summary>
    /// Resolves which SoundFont to use. An explicit choice wins; otherwise the newest file
    /// found in the search folders, so dropping one in is enough to select it.
    /// </summary>
    public static SoundFontStatus Resolve(string? preferredPath)
    {
        if (!string.IsNullOrWhiteSpace(preferredPath))
        {
            if (File.Exists(preferredPath))
            {
                return Describe(preferredPath);
            }
            return new SoundFontStatus(null, 0, $"The chosen soundfont is missing: {preferredPath}");
        }

        FileInfo? best = null;
        foreach (string folder in SearchFolders())
        {
            if (!Directory.Exists(folder))
            {
                continue;
            }
            foreach (string candidate in Directory.EnumerateFiles(folder, "*.sf2", SearchOption.TopDirectoryOnly))
            {
                FileInfo info = new(candidate);
                if (best is null || info.LastWriteTimeUtc > best.LastWriteTimeUtc)
                {
                    best = info;
                }
            }
            if (best is not null)
            {
                // First folder that has anything wins, so a per-user font is not beaten by a
                // newer shipped one.
                break;
            }
        }

        if (best is null)
        {
            return new SoundFontStatus(
                null,
                0,
                "No soundfont installed. Run scripts\\install-soundfont.ps1, or choose a .sf2 file.");
        }
        return Describe(best.FullName);
    }

    private static SoundFontStatus Describe(string path)
    {
        long bytes;
        try
        {
            bytes = new FileInfo(path).Length;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            return new SoundFontStatus(null, 0, $"Could not read {System.IO.Path.GetFileName(path)}: {error.Message}");
        }

        if (!path.EndsWith(".sf2", StringComparison.OrdinalIgnoreCase))
        {
            // .sf3 is a compressed variant that MeltySynth cannot read. Say so, rather than
            // throwing an unexplained parse error from deep inside the loader.
            return new SoundFontStatus(
                null,
                bytes,
                $"{System.IO.Path.GetFileName(path)} is not a .sf2 file. The built-in synth reads SoundFont2 only.");
        }
        return new SoundFontStatus(path, bytes, null);
    }

    /// <summary>
    /// Loads a SoundFont, reporting failure as a status rather than an exception. The result is
    /// immutable and safe to share between synthesisers on different threads.
    /// </summary>
    public static (SoundFont? Font, SoundFontStatus Status) Load(string? preferredPath)
    {
        SoundFontStatus status = Resolve(preferredPath);
        if (!status.IsAvailable)
        {
            return (null, status);
        }

        try
        {
            return (new SoundFont(status.Path!), status);
        }
        catch (Exception error)
        {
            return (null, status with
            {
                Problem = $"Could not load {status.Name}: {error.Message}"
            });
        }
    }
}
