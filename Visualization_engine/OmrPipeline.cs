using System.ComponentModel;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

[JsonConverter(typeof(JsonStringEnumConverter<OmrEngine>))]
public enum OmrEngine
{
    Homr,
    Zeus,
    MusicXml,
    DirectMidi
}

public sealed class TempoChange
{
    [JsonPropertyName("start_beat")]
    public double StartBeat { get; init; }

    [JsonPropertyName("bpm")]
    public double Bpm { get; init; }
}

public sealed class MusicNote
{
    [JsonPropertyName("pitch")]
    public string Pitch { get; init; } = string.Empty;

    [JsonPropertyName("midi_pitch")]
    public int MidiPitch { get; init; }

    [JsonPropertyName("start_beat")]
    public double StartBeat { get; init; }

    [JsonPropertyName("duration_beats")]
    public double DurationBeats { get; init; }

    [JsonPropertyName("start_seconds")]
    public double StartSeconds { get; init; }

    [JsonPropertyName("duration_seconds")]
    public double DurationSeconds { get; init; }

    [JsonPropertyName("part_index")]
    public int PartIndex { get; init; }

    [JsonPropertyName("staff_index")]
    public int StaffIndex { get; init; }

    [JsonPropertyName("voice_identifier")]
    public string VoiceIdentifier { get; init; } = string.Empty;
}

public sealed class OmrResult
{
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; init; }

    [JsonPropertyName("engine")]
    public OmrEngine Engine { get; init; }

    [JsonPropertyName("engine_revision")]
    public string EngineRevision { get; init; } = string.Empty;

    [JsonPropertyName("tempo_changes")]
    public List<TempoChange> TempoChanges { get; init; } = [];

    [JsonPropertyName("notes")]
    public List<MusicNote> Notes { get; init; } = [];
}

public class OmrPipelineException : Exception
{
    public OmrPipelineException(
        string message,
        string? errorCode = null,
        string? stage = null,
        int? exitCode = null,
        int? page = null,
        string? standardError = null)
        : base(message)
    {
        ErrorCode = errorCode;
        Stage = stage;
        ExitCode = exitCode;
        Page = page;
        StandardError = standardError ?? string.Empty;
    }

    public OmrPipelineException(
        string message,
        Exception innerException,
        string? errorCode = null,
        string? stage = null,
        int? exitCode = null,
        int? page = null,
        string? standardError = null)
        : base(message, innerException)
    {
        ErrorCode = errorCode;
        Stage = stage;
        ExitCode = exitCode;
        Page = page;
        StandardError = standardError ?? string.Empty;
    }

    public string? ErrorCode { get; }
    public string? Stage { get; }
    public int? ExitCode { get; }
    public int? Page { get; }
    public string StandardError { get; }
}

public static class OmrPipeline
{
    private const string ProgressPrefix = "SHEET2PLAY_PROGRESS:";
    public const int SchemaVersion = 2;
    public const string HomrEngineRevision = "homr-0.7.0.post34+2d0c0a6";
    public const string HomrModelRevision = "homr-default-models";
    public const string ZeusEngineRevision =
        "df0d842596ccd199882ff958e628d59327ca6cba";
    public const string ZeusModelRevision =
        "2024-02-12";
    public const string ZeusModelSha256 =
        "df0d842596ccd199882ff958e628d59327ca6cba";

    private static readonly TimeSpan DefaultTimeout = TimeSpan.FromMinutes(30);
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = false,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters = { new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase) }
    };

    public static OmrResult Run(
        string inputPath,
        OmrEngine engine,
        string? bridgeScriptPath = null,
        string pythonExecutable = "python",
        TimeSpan? timeout = null,
        CancellationToken cancellationToken = default,
        IProgress<OmrProgress>? progress = null)
    {
        return RunAsync(
                inputPath,
                engine,
                bridgeScriptPath,
                pythonExecutable,
                timeout,
                cancellationToken,
                progress)
            .GetAwaiter()
            .GetResult();
    }

    public static async Task<OmrResult> RunAsync(
        string inputPath,
        OmrEngine engine,
        string? bridgeScriptPath = null,
        string pythonExecutable = "python",
        TimeSpan? timeout = null,
        CancellationToken cancellationToken = default,
        IProgress<OmrProgress>? progress = null)
    {
        if (!Enum.IsDefined(engine))
        {
            throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.");
        }

        string validatedInputPath = ValidateFilePath(inputPath, "OMR input");
        string validatedBridgePath = ValidateFilePath(
            bridgeScriptPath ?? GetDefaultBridgeScriptPath(),
            "Python bridge script");

        if (string.IsNullOrWhiteSpace(pythonExecutable))
        {
            throw new ArgumentException("Python executable cannot be empty.", nameof(pythonExecutable));
        }

        TimeSpan effectiveTimeout = timeout ?? DefaultTimeout;
        if (effectiveTimeout <= TimeSpan.Zero && effectiveTimeout != Timeout.InfiniteTimeSpan)
        {
            throw new ArgumentOutOfRangeException(
                nameof(timeout),
                timeout,
                "Timeout must be positive or Timeout.InfiniteTimeSpan.");
        }

        bool useManagedEngineRuntime = bridgeScriptPath is null && pythonExecutable == "python";
        string effectivePythonExecutable = useManagedEngineRuntime
            ? ResolveEnginePythonExecutable(validatedBridgePath, engine)
            : pythonExecutable;
        if (useManagedEngineRuntime && !File.Exists(effectivePythonExecutable))
        {
            throw new OmrPipelineException(
                $"The {GetEngineName(engine)} Python runtime was not found at " +
                $"'{effectivePythonExecutable}'. {GetRuntimeSetupInstruction(engine)}",
                errorCode: "RUNTIME_MISSING",
                stage: "runtime_start");
        }
        ProcessStartInfo startInfo = CreateStartInfo(
            effectivePythonExecutable,
            validatedBridgePath,
            validatedInputPath,
            engine);

        using Process process = new() { StartInfo = startInfo };
        try
        {
            if (!process.Start())
            {
                throw new OmrPipelineException(
                    $"Failed to start Python executable '{effectivePythonExecutable}'.");
            }
            process.StandardInput.Close();
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            throw new OmrPipelineException(
                $"Could not start Python executable '{effectivePythonExecutable}'. " +
                    GetRuntimeSetupInstruction(engine),
                exception,
                errorCode: "RUNTIME_MISSING",
                stage: "runtime_start");
        }

        Task<string> standardOutputTask = process.StandardOutput.ReadToEndAsync();
        Task<string> standardErrorTask = ConsumeStandardErrorAsync(
            process.StandardError,
            progress);

        using CancellationTokenSource? timeoutSource = CreateTimeoutSource(effectiveTimeout);
        using CancellationTokenSource linkedSource = timeoutSource is null
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken)
            : CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeoutSource.Token);

        try
        {
            await process.WaitForExitAsync(linkedSource.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            KillProcessTree(process);
            await WaitForTerminationAsync(process).ConfigureAwait(false);
            await Task.WhenAll(standardOutputTask, standardErrorTask).ConfigureAwait(false);

            if (timeoutSource?.IsCancellationRequested == true &&
                !cancellationToken.IsCancellationRequested)
            {
                throw new TimeoutException(
                    $"{engine} OMR processing exceeded the timeout of {effectiveTimeout}.");
            }

            throw;
        }

        string standardOutput = await standardOutputTask.ConfigureAwait(false);
        string standardError = await standardErrorTask.ConfigureAwait(false);
        if (process.ExitCode != 0)
        {
            StructuredBridgeError? bridgeError = ParseStructuredError(standardError);
            string failureMessage = bridgeError is null
                ? $"Python {engine} OMR bridge failed with exit code {process.ExitCode}." +
                  FormatStandardError(standardError)
                : FormatStructuredFailure(engine, process.ExitCode, bridgeError);
            throw new OmrPipelineException(
                failureMessage,
                errorCode: bridgeError?.Code,
                stage: bridgeError?.Stage,
                exitCode: process.ExitCode,
                page: bridgeError?.Page,
                standardError: standardError);
        }
        if (string.IsNullOrWhiteSpace(standardOutput))
        {
            throw new OmrPipelineException(
                $"Python {engine} OMR bridge returned no JSON." +
                FormatStandardError(standardError),
                standardError: standardError);
        }

        OmrResult result;
        try
        {
            result = JsonSerializer.Deserialize<OmrResult>(standardOutput, JsonOptions)
                ?? throw new JsonException("The JSON document contained null.");
        }
        catch (JsonException exception)
        {
            throw new OmrPipelineException(
                "Python OMR bridge returned invalid result JSON. " +
                $"Output: {Truncate(standardOutput, 2_000)}" +
                FormatStandardError(standardError),
                exception,
                standardError: standardError);
        }

        ValidateResult(result, engine);
        return result;
    }

    private static async Task<string> ConsumeStandardErrorAsync(
        StreamReader reader,
        IProgress<OmrProgress>? progress)
    {
        StringBuilder captured = new();
        while (await reader.ReadLineAsync().ConfigureAwait(false) is { } line)
        {
            captured.AppendLine(line);
            Console.Error.WriteLine(line);
            OmrProgress? update = ParseProgress(line);
            if (update is not null)
            {
                progress?.Report(update);
            }
        }
        return captured.ToString();
    }

    internal static OmrProgress? ParseProgress(string line)
    {
        if (!line.StartsWith(ProgressPrefix, StringComparison.Ordinal))
        {
            return null;
        }
        try
        {
            OmrProgress? progress = JsonSerializer.Deserialize<OmrProgress>(
                line[ProgressPrefix.Length..],
                JsonOptions);
            if (progress is null || progress.SchemaVersion != 1 ||
                string.IsNullOrWhiteSpace(progress.Stage) ||
                string.IsNullOrWhiteSpace(progress.Status) ||
                string.IsNullOrWhiteSpace(progress.Message))
            {
                return null;
            }
            return progress;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    public static string GetEngineRevision(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => HomrEngineRevision,
        OmrEngine.Zeus => ZeusEngineRevision,
        _ => throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.")
    };

    public static string GetModelRevision(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => HomrModelRevision,
        OmrEngine.Zeus => ZeusModelRevision,
        _ => throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.")
    };

    public static string GetEngineName(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => "homr",
        OmrEngine.Zeus => "zeus",
        OmrEngine.MusicXml => "musicxml",
        OmrEngine.DirectMidi => "directmidi",
        _ => throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.")
    };

    public static string GetSettingsFingerprint(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => "cuda|CUDAExecutionProvider|homr-default-300-dpi|120",
        OmrEngine.Zeus =>
            "cuda|1485x1050|300dpi|beam3-then-grammar1|max2048|numeric-tempo-or-120",
        OmrEngine.MusicXml => "musicxml-native-120",
        OmrEngine.DirectMidi => "direct-midi-playback",
        _ => throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.")
    };

    private static ProcessStartInfo CreateStartInfo(
        string pythonExecutable,
        string bridgeScriptPath,
        string inputPath,
        OmrEngine engine)
    {
        ProcessStartInfo startInfo = new()
        {
            FileName = pythonExecutable,
            WorkingDirectory = Path.GetDirectoryName(bridgeScriptPath)
                ?? throw new InvalidOperationException("Bridge script has no parent directory."),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add(bridgeScriptPath);
        startInfo.ArgumentList.Add("--engine");
        startInfo.ArgumentList.Add(GetEngineName(engine));
        startInfo.ArgumentList.Add(inputPath);
        startInfo.Environment["PYTHONUNBUFFERED"] = "1";
        return startInfo;
    }

    private static string GetDefaultBridgeScriptPath()
    {
        return Path.Combine(AppContext.BaseDirectory, "Bridge", "bridge.py");
    }

    internal static string ResolveEnginePythonExecutable(
        string bridgeScriptPath,
        OmrEngine engine)
    {
        string bridgeDirectory = Path.GetDirectoryName(bridgeScriptPath)
            ?? throw new InvalidOperationException("Bridge script has no parent directory.");
        DirectoryInfo? directory = new(bridgeDirectory);
        while (directory is not null)
        {
            string candidate = engine switch
            {
                OmrEngine.Homr => Path.Combine(
                    directory.FullName,
                    "Bridge",
                    ".venv-homr-gpu",
                    "Scripts",
                    "python.exe"),
                OmrEngine.Zeus => Path.Combine(
                    directory.FullName,
                    "Research",
                    "omr",
                    ".venv",
                    "Scripts",
                    "python.exe"),
                _ => throw new ArgumentOutOfRangeException(
                    nameof(engine), engine, "Unknown OMR engine.")
            };
            if (File.Exists(candidate))
            {
                return candidate;
            }

            if (engine == OmrEngine.Homr)
            {
                string directCandidate = Path.Combine(
                    directory.FullName,
                    ".venv-homr-gpu",
                    "Scripts",
                    "python.exe");
                if (File.Exists(directCandidate))
                {
                    return directCandidate;
                }
            }
            directory = directory.Parent;
        }

        return engine switch
        {
            OmrEngine.Homr => Path.Combine(
                bridgeDirectory, ".venv-homr-gpu", "Scripts", "python.exe"),
            OmrEngine.Zeus => Path.GetFullPath(Path.Combine(
                bridgeDirectory,
                "..",
                "Research",
                "omr",
                ".venv",
                "Scripts",
                "python.exe")),
            _ => throw new ArgumentOutOfRangeException(
                nameof(engine), engine, "Unknown OMR engine.")
        };
    }

    internal static string GetRuntimeSetupInstruction(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => "Run Bridge/setup_gpu.ps1 first.",
        OmrEngine.Zeus =>
            "Run Research/omr/setup_research.ps1 -Profile Inference first.",
        _ => throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.")
    };

    private static StructuredBridgeError? ParseStructuredError(string standardError)
    {
        const string prefix = "SHEET2PLAY_ERROR:";
        foreach (string line in standardError.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).Reverse())
        {
            int prefixIndex = line.IndexOf(prefix, StringComparison.Ordinal);
            if (prefixIndex < 0)
            {
                continue;
            }
            try
            {
                return JsonSerializer.Deserialize<StructuredBridgeError>(
                    line[(prefixIndex + prefix.Length)..],
                    JsonOptions);
            }
            catch (JsonException)
            {
                return null;
            }
        }
        return null;
    }

    private static string FormatStructuredFailure(
        OmrEngine engine,
        int exitCode,
        StructuredBridgeError error)
    {
        string code = string.IsNullOrWhiteSpace(error.Code) ? "UNKNOWN" : error.Code;
        string stage = string.IsNullOrWhiteSpace(error.Stage) ? "unknown" : error.Stage;
        string page = error.Page is null ? string.Empty : $", page {error.Page}";
        string detail = string.IsNullOrWhiteSpace(error.Message)
            ? "The bridge did not provide an error message."
            : error.Message;
        return $"{engine} OMR failed [{code}] at {stage}{page} " +
               $"(exit code {exitCode}): {detail}";
    }

    private static string ValidateFilePath(string path, string description)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ArgumentException($"{description} path cannot be empty.", nameof(path));
        }

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(path);
        }
        catch (Exception exception) when (
            exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            throw new ArgumentException(
                $"{description} path is invalid: {path}", nameof(path), exception);
        }

        if (!File.Exists(fullPath))
        {
            throw new FileNotFoundException($"{description} file was not found.", fullPath);
        }
        return fullPath;
    }

    private static CancellationTokenSource? CreateTimeoutSource(TimeSpan timeout)
    {
        if (timeout == Timeout.InfiniteTimeSpan)
        {
            return null;
        }
        CancellationTokenSource source = new();
        source.CancelAfter(timeout);
        return source;
    }

    private static void KillProcessTree(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
        }
        catch (Win32Exception)
        {
        }
    }

    private static async Task WaitForTerminationAsync(Process process)
    {
        try
        {
            await process.WaitForExitAsync().ConfigureAwait(false);
        }
        catch (InvalidOperationException)
        {
        }
    }

    private static void ValidateResult(OmrResult result, OmrEngine requestedEngine)
    {
        if (result.SchemaVersion != SchemaVersion)
        {
            throw new OmrPipelineException(
                $"Unsupported bridge schema {result.SchemaVersion}; expected {SchemaVersion}.");
        }
        if (result.Engine != requestedEngine)
        {
            throw new OmrPipelineException(
                $"Bridge returned engine {result.Engine} after {requestedEngine} was requested.");
        }

        string expectedRevision = GetEngineRevision(requestedEngine);
        if (!string.Equals(result.EngineRevision, expectedRevision, StringComparison.Ordinal))
        {
            throw new OmrPipelineException(
                $"Bridge engine revision '{result.EngineRevision}' does not match " +
                $"expected revision '{expectedRevision}'.");
        }
        if (result.TempoChanges.Count == 0)
        {
            throw new OmrPipelineException("Bridge result contains no tempo map.");
        }

        double previousBeat = -1;
        for (int index = 0; index < result.TempoChanges.Count; index++)
        {
            TempoChange change = result.TempoChanges[index]
                ?? throw new OmrPipelineException($"Tempo change at index {index} is null.");
            if (!double.IsFinite(change.StartBeat) || change.StartBeat < 0 ||
                change.StartBeat < previousBeat)
            {
                throw new OmrPipelineException(
                    $"Tempo change at index {index} has invalid start_beat {change.StartBeat}.");
            }
            if (!double.IsFinite(change.Bpm) || change.Bpm <= 0)
            {
                throw new OmrPipelineException(
                    $"Tempo change at index {index} has invalid BPM {change.Bpm}.");
            }
            previousBeat = change.StartBeat;
        }
        if (Math.Abs(result.TempoChanges[0].StartBeat) > 1e-9)
        {
            throw new OmrPipelineException("Tempo map must start at beat zero.");
        }
        if (result.Notes.Count == 0)
        {
            throw new OmrPipelineException("Bridge result contains no notes.");
        }

        for (int index = 0; index < result.Notes.Count; index++)
        {
            MusicNote note = result.Notes[index]
                ?? throw new OmrPipelineException($"JSON note at index {index} is null.");
            if (string.IsNullOrWhiteSpace(note.Pitch))
            {
                throw new OmrPipelineException($"JSON note at index {index} has no pitch.");
            }
            if (note.MidiPitch is < 0 or > 127)
            {
                throw new OmrPipelineException(
                    $"JSON note at index {index} has invalid MIDI pitch {note.MidiPitch}.");
            }
            ValidateNonNegative(note.StartBeat, "start_beat", index);
            ValidatePositive(note.DurationBeats, "duration_beats", index);
            ValidateNonNegative(note.StartSeconds, "start_seconds", index);
            ValidatePositive(note.DurationSeconds, "duration_seconds", index);
            if (note.PartIndex < 0 || note.StaffIndex < 0)
            {
                throw new OmrPipelineException(
                    $"JSON note at index {index} has a negative part or staff index.");
            }
            if (string.IsNullOrWhiteSpace(note.VoiceIdentifier))
            {
                throw new OmrPipelineException(
                    $"JSON note at index {index} has no voice identifier.");
            }
        }
    }

    private static void ValidateNonNegative(double value, string name, int index)
    {
        if (!double.IsFinite(value) || value < 0)
        {
            throw new OmrPipelineException(
                $"JSON note at index {index} has invalid {name} {value}.");
        }
    }

    private static void ValidatePositive(double value, string name, int index)
    {
        if (!double.IsFinite(value) || value <= 0)
        {
            throw new OmrPipelineException(
                $"JSON note at index {index} has invalid {name} {value}; expected a positive value.");
        }
    }

    private static string FormatStandardError(string standardError)
    {
        return string.IsNullOrWhiteSpace(standardError)
            ? string.Empty
            : $" stderr: {Truncate(standardError.Trim(), 8_000)}";
    }

    private static string Truncate(string value, int maximumLength)
    {
        return value.Length <= maximumLength
            ? value
            : $"{value[..maximumLength]} [truncated]";
    }

    private sealed class StructuredBridgeError
    {
        [JsonPropertyName("code")]
        public string? Code { get; init; }

        [JsonPropertyName("stage")]
        public string? Stage { get; init; }

        [JsonPropertyName("message")]
        public string? Message { get; init; }

        [JsonPropertyName("page")]
        public int? Page { get; init; }
    }
}
