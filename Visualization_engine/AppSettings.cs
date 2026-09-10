using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

public static class AppSettingsStore
{
    /// <summary>
    /// Milliseconds by which MIDI events are sent ahead of their visual time, to cover
    /// the synthesiser's output latency. 55 was measured by ear against VirtualMIDISynth
    /// on the author's machine; it is not universal, because the true figure depends on
    /// the output chain. Bluetooth output alone adds well over 100 ms, so this is a
    /// starting point to be tuned, not a constant.
    /// </summary>
    public const int DefaultAudioOffsetMilliseconds = 55;

    public const int MinimumAudioOffsetMilliseconds = 0;
    public const int MaximumAudioOffsetMilliseconds = 500;

    /// <summary>
    /// Marks the built-in synth's offset as never having been calibrated, so it can follow the
    /// buffer configuration instead of a stored number.
    /// </summary>
    /// <remarks>
    /// The offset above is the user's own by-ear measurement against VirtualMIDISynth, and it
    /// means something different on each backend: in-process synthesis has a fraction of the
    /// latency, so reusing that number would silently mis-time the new path and reusing the new
    /// one would destroy their calibration. They are stored separately for that reason.
    /// </remarks>
    public const int UnsetSynthAudioOffset = -1;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters =
        {
            new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase),
            new JsonStringEnumConverter<AudioBackend>(JsonNamingPolicy.CamelCase)
        }
    };

    public static OmrEngine LoadEngine()
    {
        return LoadEngineFromPath(GetSettingsPath());
    }

    internal static OmrEngine LoadEngineFromPath(string settingsPath)
    {
        return ReadOrRepair(settingsPath).OmrEngine;
    }

    public static int LoadAudioOffsetMilliseconds()
    {
        return LoadAudioOffsetFromPath(GetSettingsPath());
    }

    internal static int LoadAudioOffsetFromPath(string settingsPath)
    {
        return ReadOrRepair(settingsPath).AudioOffsetMilliseconds;
    }

    public static void SaveEngine(OmrEngine engine)
    {
        SaveEngineToPath(engine, GetSettingsPath());
    }

    internal static void SaveEngineToPath(OmrEngine engine, string settingsPath)
    {
        if (!Enum.IsDefined(engine))
        {
            throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.");
        }

        // Read first so saving one field does not silently reset the other.
        Write(ReadOrRepair(settingsPath) with { OmrEngine = engine }, settingsPath);
    }

    public static void SaveAudioOffsetMilliseconds(int offsetMilliseconds)
    {
        SaveAudioOffsetToPath(offsetMilliseconds, GetSettingsPath());
    }

    internal static void SaveAudioOffsetToPath(int offsetMilliseconds, string settingsPath)
    {
        Write(
            ReadOrRepair(settingsPath) with { AudioOffsetMilliseconds = Clamp(offsetMilliseconds) },
            settingsPath);
    }

    public static AudioBackend LoadAudioBackend() => LoadAudioBackendFromPath(GetSettingsPath());

    internal static AudioBackend LoadAudioBackendFromPath(string settingsPath) =>
        ReadOrRepair(settingsPath).AudioBackend;

    public static void SaveAudioBackend(AudioBackend backend) =>
        SaveAudioBackendToPath(backend, GetSettingsPath());

    internal static void SaveAudioBackendToPath(AudioBackend backend, string settingsPath)
    {
        if (!Enum.IsDefined(backend))
        {
            throw new ArgumentOutOfRangeException(nameof(backend), backend, "Unknown audio backend.");
        }
        Write(ReadOrRepair(settingsPath) with { AudioBackend = backend }, settingsPath);
    }

    public static string? LoadSoundFontPath() => LoadSoundFontPathFromPath(GetSettingsPath());

    internal static string? LoadSoundFontPathFromPath(string settingsPath) =>
        ReadOrRepair(settingsPath).SoundFontPath;

    public static void SaveSoundFontPath(string? path) =>
        SaveSoundFontPathToPath(path, GetSettingsPath());

    internal static void SaveSoundFontPathToPath(string? path, string settingsPath)
    {
        string? trimmed = string.IsNullOrWhiteSpace(path) ? null : path.Trim();
        Write(ReadOrRepair(settingsPath) with { SoundFontPath = trimmed }, settingsPath);
    }

    /// <summary>
    /// The built-in synth's offset, or <see cref="UnsetSynthAudioOffset"/> when the user has
    /// never calibrated it and it should follow the audio buffer instead.
    /// </summary>
    public static int LoadSynthAudioOffsetMilliseconds() =>
        LoadSynthAudioOffsetFromPath(GetSettingsPath());

    internal static int LoadSynthAudioOffsetFromPath(string settingsPath) =>
        ReadOrRepair(settingsPath).SynthAudioOffsetMilliseconds;

    public static void SaveSynthAudioOffsetMilliseconds(int offsetMilliseconds) =>
        SaveSynthAudioOffsetToPath(offsetMilliseconds, GetSettingsPath());

    internal static void SaveSynthAudioOffsetToPath(int offsetMilliseconds, string settingsPath)
    {
        Write(
            ReadOrRepair(settingsPath) with { SynthAudioOffsetMilliseconds = Clamp(offsetMilliseconds) },
            settingsPath);
    }

    /// <summary>
    /// Offset to use for a backend: the user's stored value, or for the built-in synth before
    /// they have touched it, whatever the audio buffer actually costs.
    /// </summary>
    /// <remarks>
    /// A computed default rather than a guessed one - it is a measured property of the buffer
    /// configuration, not somebody's opinion about what sounds right.
    /// </remarks>
    public static int ResolveAudioOffsetMilliseconds(AudioBackend backend, double bufferedSeconds)
    {
        if (backend == AudioBackend.MidiDevice)
        {
            return LoadAudioOffsetMilliseconds();
        }

        int stored = LoadSynthAudioOffsetMilliseconds();
        if (stored != UnsetSynthAudioOffset)
        {
            return Clamp(stored);
        }
        return Clamp((int)Math.Ceiling(bufferedSeconds * 1000.0));
    }

    public static int Clamp(int offsetMilliseconds)
    {
        return Math.Clamp(
            offsetMilliseconds,
            MinimumAudioOffsetMilliseconds,
            MaximumAudioOffsetMilliseconds);
    }

    public static string GetSettingsPath()
    {
        string localApplicationData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        if (string.IsNullOrWhiteSpace(localApplicationData))
        {
            throw new InvalidOperationException(
                "Windows LocalApplicationData directory is unavailable.");
        }
        return Path.Combine(localApplicationData, "Sheet2Play", "settings.json");
    }

    /// <summary>
    /// Reads the settings file, rewriting it with defaults if it is missing, unreadable
    /// or holds an unknown engine. A file written by an older build that lacks
    /// audio_offset_milliseconds still loads: the missing member falls back to the
    /// record's default rather than failing the whole read.
    /// </summary>
    private static AppSettings ReadOrRepair(string settingsPath)
    {
        AppSettings? settings = TryRead(settingsPath);
        if (settings is not null)
        {
            // The synth offset is deliberately not clamped here: UnsetSynthAudioOffset is -1,
            // and clamping would turn "never calibrated" into a real 0 ms.
            return settings with { AudioOffsetMilliseconds = Clamp(settings.AudioOffsetMilliseconds) };
        }

        AppSettings defaults = new(OmrEngine.Homr, DefaultAudioOffsetMilliseconds);
        try
        {
            Write(defaults, settingsPath);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine($"[SETTINGS] Could not rewrite legacy settings: {exception.Message}");
        }
        return defaults;
    }

    private static AppSettings? TryRead(string settingsPath)
    {
        if (!File.Exists(settingsPath))
        {
            return null;
        }

        try
        {
            AppSettings? settings = JsonSerializer.Deserialize<AppSettings>(
                File.ReadAllText(settingsPath),
                JsonOptions);
            return settings is not null && Enum.IsDefined(settings.OmrEngine) ? settings : null;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine(
                $"[SETTINGS] Could not read {settingsPath}; using homr. {exception.Message}");
            return null;
        }
    }

    private static void Write(AppSettings settings, string settingsPath)
    {
        string directory = Path.GetDirectoryName(settingsPath)
            ?? throw new InvalidOperationException("Settings path has no parent directory.");
        Directory.CreateDirectory(directory);
        string temporaryPath = Path.Combine(
            directory,
            $".{Path.GetFileName(settingsPath)}.{Guid.NewGuid():N}.tmp");
        try
        {
            string json = JsonSerializer.Serialize(settings, JsonOptions);
            File.WriteAllText(temporaryPath, json);
            File.Move(temporaryPath, settingsPath, overwrite: true);
        }
        finally
        {
            try
            {
                if (File.Exists(temporaryPath))
                {
                    File.Delete(temporaryPath);
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    private sealed record AppSettings(
        OmrEngine OmrEngine,
        int AudioOffsetMilliseconds = DefaultAudioOffsetMilliseconds,
        AudioBackend AudioBackend = AudioBackend.SoundFont,
        int SynthAudioOffsetMilliseconds = UnsetSynthAudioOffset,
        string? SoundFontPath = null);
}
