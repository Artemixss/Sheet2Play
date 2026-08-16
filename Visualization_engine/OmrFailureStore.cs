using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

public sealed class KnownOmrFailureException : OmrPipelineException
{
    public KnownOmrFailureException(OmrFailureEntry entry)
        : base(
            $"Known deterministic {entry.Engine} failure: {entry.Message}",
            errorCode: entry.ErrorCode,
            stage: entry.Stage,
            page: entry.Page)
    {
        Entry = entry;
    }

    public OmrFailureEntry Entry { get; }
}

public sealed record OmrFailureEntry(
    string SourceSha256,
    OmrEngine Engine,
    string EngineRevision,
    string ModelRevision,
    int BridgeSchemaVersion,
    string SettingsFingerprint,
    string ErrorCode,
    string Stage,
    int? Page,
    string Message,
    DateTimeOffset CreatedUtc,
    DateTimeOffset LastAccessUtc);

public static class OmrFailureStore
{
    private const int MaximumEntries = 50;
    private const int MaximumStoredMessageLength = 2_000;
    private static readonly HashSet<string> DeterministicNormalizationStages = new(
        StringComparer.Ordinal)
    {
        "semantic_validation",
        "playback_normalization",
        "output_validation",
        "note_validation",
        "round_trip_validation"
    };
    private static readonly object Gate = new();
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters = { new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase) }
    };
    public static string DefaultPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Sheet2Play",
        "failed-omr.json");

    public static bool TryGet(
        string sourceSha256,
        OmrEngine engine,
        out OmrFailureEntry? entry,
        string? storePath = null)
    {
        if (engine != OmrEngine.Zeus)
        {
            entry = null;
            return false;
        }

        string path = storePath ?? DefaultPath;
        lock (Gate)
        {
            List<OmrFailureEntry> entries = ReadEntries(path);
            int index = entries.FindIndex(item => Matches(item, sourceSha256, engine));
            if (index < 0)
            {
                entry = null;
                return false;
            }
            entry = entries[index] with { LastAccessUtc = DateTimeOffset.UtcNow };
            entries[index] = entry;
            TryWriteEntries(path, entries);
            return true;
        }
    }

    public static void Remember(
        string sourceSha256,
        OmrEngine engine,
        OmrPipelineException exception,
        string? storePath = null)
    {
        ArgumentNullException.ThrowIfNull(exception);
        if (!IsDeterministicFailure(engine, exception))
        {
            return;
        }

        string path = storePath ?? DefaultPath;
        string errorCode = exception.ErrorCode!;
        string stage = string.IsNullOrWhiteSpace(exception.Stage)
            ? "unknown"
            : exception.Stage;
        string message = string.IsNullOrWhiteSpace(exception.Message)
            ? errorCode
            : exception.Message;
        if (message.Length > MaximumStoredMessageLength)
        {
            message = message[..MaximumStoredMessageLength];
        }

        lock (Gate)
        {
            DateTimeOffset now = DateTimeOffset.UtcNow;
            List<OmrFailureEntry> entries = ReadEntries(path);
            entries.RemoveAll(item => Matches(item, sourceSha256, engine));
            entries.Add(new OmrFailureEntry(
                sourceSha256,
                engine,
                OmrPipeline.GetEngineRevision(engine),
                OmrPipeline.GetModelRevision(engine),
                OmrPipeline.SchemaVersion,
                OmrPipeline.GetSettingsFingerprint(engine),
                errorCode,
                stage,
                exception.Page,
                message,
                now,
                now));
            TryWriteEntries(
                path,
                entries
                    .OrderByDescending(item => item.LastAccessUtc)
                    .Take(MaximumEntries)
                    .ToArray());
        }
    }

    public static void Remove(
        string sourceSha256,
        OmrEngine engine,
        string? storePath = null)
    {
        string path = storePath ?? DefaultPath;
        lock (Gate)
        {
            List<OmrFailureEntry> entries = ReadEntries(path);
            if (entries.RemoveAll(item => Matches(item, sourceSha256, engine)) > 0)
            {
                TryWriteEntries(path, entries);
            }
        }
    }

    internal static IReadOnlyList<OmrFailureEntry> ReadForTesting(string path) =>
        ReadEntries(path);

    internal static bool IsDeterministicFailure(
        OmrEngine engine,
        OmrPipelineException exception)
    {
        if (engine != OmrEngine.Zeus ||
            string.IsNullOrWhiteSpace(exception.ErrorCode))
        {
            return false;
        }

        return exception.ErrorCode switch
        {
            "ZEUS_OUTPUT_TRUNCATED" or "KERN_INVALID" or "KERN_PARSE_FAILED" => true,
            "NORMALIZATION_FAILED" =>
                !string.IsNullOrWhiteSpace(exception.Stage) &&
                DeterministicNormalizationStages.Contains(exception.Stage),
            _ => false
        };
    }

    private static bool Matches(
        OmrFailureEntry entry,
        string sourceSha256,
        OmrEngine engine) =>
        string.Equals(entry.SourceSha256, sourceSha256, StringComparison.Ordinal) &&
        entry.Engine == engine &&
        entry.EngineRevision == OmrPipeline.GetEngineRevision(engine) &&
        entry.ModelRevision == OmrPipeline.GetModelRevision(engine) &&
        entry.BridgeSchemaVersion == OmrPipeline.SchemaVersion &&
        entry.SettingsFingerprint == OmrPipeline.GetSettingsFingerprint(engine);

    private static List<OmrFailureEntry> ReadEntries(string path)
    {
        try
        {
            if (!File.Exists(path))
            {
                return [];
            }
            return JsonSerializer.Deserialize<List<OmrFailureEntry>>(
                       File.ReadAllText(path),
                       JsonOptions) ?? [];
        }
        catch (JsonException)
        {
            return MigrateLegacyEntries(path);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[FAILURE MEMORY] Ignoring invalid store: {exception.Message}");
            return [];
        }
    }

    private static List<OmrFailureEntry> MigrateLegacyEntries(string path)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            if (document.RootElement.ValueKind != JsonValueKind.Array)
            {
                return [];
            }
            List<OmrFailureEntry> retained = [];
            foreach (JsonElement element in document.RootElement.EnumerateArray())
            {
                if (element.TryGetProperty("engine", out JsonElement engineElement) &&
                    engineElement.ValueKind == JsonValueKind.String &&
                    engineElement.GetString() is { } engineName &&
                    (engineName.Equals("oemer", StringComparison.OrdinalIgnoreCase) ||
                     engineName.Equals("smt", StringComparison.OrdinalIgnoreCase) ||
                     engineName.Equals("clarity", StringComparison.OrdinalIgnoreCase)))
                {
                    continue;
                }
                try
                {
                    OmrFailureEntry? entry = element.Deserialize<OmrFailureEntry>(JsonOptions);
                    if (entry is not null)
                    {
                        retained.Add(entry);
                    }
                }
                catch (JsonException)
                {
                }
            }
            TryWriteEntries(path, retained);
            return retained;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine(
                $"[FAILURE MEMORY] Could not migrate legacy entries: {exception.Message}");
            return [];
        }
    }

    private static void TryWriteEntries(string path, IReadOnlyCollection<OmrFailureEntry> entries)
    {
        string? directory = Path.GetDirectoryName(path);
        if (string.IsNullOrWhiteSpace(directory))
        {
            return;
        }
        string temporaryPath = Path.Combine(
            directory,
            $".{Path.GetFileName(path)}.{Guid.NewGuid():N}.tmp");
        try
        {
            Directory.CreateDirectory(directory);
            File.WriteAllText(temporaryPath, JsonSerializer.Serialize(entries, JsonOptions));
            File.Move(temporaryPath, path, overwrite: true);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[FAILURE MEMORY] Save failed: {exception.Message}");
        }
        finally
        {
            try
            {
                File.Delete(temporaryPath);
            }
            catch (Exception exception) when (
                exception is IOException or UnauthorizedAccessException)
            {
            }
        }
    }
}
