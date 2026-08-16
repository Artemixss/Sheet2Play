using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

public sealed record RecentSongEntry(
    string ManifestRelativePath,
    string DisplayName,
    OmrEngine Engine,
    DateTimeOffset LastOpenedUtc);

public static class RecentSongsStore
{
    private const int MaximumEntries = 10;
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
        "recent.json");

    public static IReadOnlyList<RecentSongEntry> Load(string? storePath = null)
    {
        lock (Gate)
        {
            return ReadEntries(storePath ?? DefaultPath)
                .OrderByDescending(entry => entry.LastOpenedUtc)
                .Take(MaximumEntries)
                .ToArray();
        }
    }

    public static void Touch(RecentSongEntry entry, string? storePath = null)
    {
        ArgumentNullException.ThrowIfNull(entry);
        string path = storePath ?? DefaultPath;
        lock (Gate)
        {
            List<RecentSongEntry> entries = ReadEntries(path);
            entries.RemoveAll(item =>
                string.Equals(
                    item.ManifestRelativePath,
                    entry.ManifestRelativePath,
                    StringComparison.OrdinalIgnoreCase));
            entries.Add(entry with { LastOpenedUtc = DateTimeOffset.UtcNow });
            WriteEntries(
                path,
                entries.OrderByDescending(item => item.LastOpenedUtc)
                    .Take(MaximumEntries)
                    .ToArray());
        }
    }

    public static void Remove(string manifestRelativePath, string? storePath = null)
    {
        string path = storePath ?? DefaultPath;
        lock (Gate)
        {
            List<RecentSongEntry> entries = ReadEntries(path);
            if (entries.RemoveAll(item => string.Equals(
                    item.ManifestRelativePath,
                    manifestRelativePath,
                    StringComparison.OrdinalIgnoreCase)) > 0)
            {
                WriteEntries(path, entries);
            }
        }
    }

    private static List<RecentSongEntry> ReadEntries(string path)
    {
        try
        {
            if (!File.Exists(path))
            {
                return [];
            }
            return JsonSerializer.Deserialize<List<RecentSongEntry>>(
                       File.ReadAllText(path), JsonOptions) ?? [];
        }
        catch (JsonException)
        {
            return MigrateLegacyEntries(path);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[RECENT SONGS] Ignoring invalid store: {exception.Message}");
            return [];
        }
    }

    private static List<RecentSongEntry> MigrateLegacyEntries(string path)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            if (document.RootElement.ValueKind != JsonValueKind.Array)
            {
                return [];
            }
            List<RecentSongEntry> retained = [];
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
                    RecentSongEntry? entry = element.Deserialize<RecentSongEntry>(JsonOptions);
                    if (entry is not null)
                    {
                        retained.Add(entry);
                    }
                }
                catch (JsonException)
                {
                }
            }
            WriteEntries(path, retained);
            return retained;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine(
                $"[RECENT SONGS] Could not migrate legacy entries: {exception.Message}");
            return [];
        }
    }

    private static void WriteEntries(string path, IReadOnlyCollection<RecentSongEntry> entries)
    {
        string directory = Path.GetDirectoryName(path)
            ?? throw new InvalidOperationException("Recent-song store has no parent directory.");
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
            Console.Error.WriteLine($"[RECENT SONGS] Save failed: {exception.Message}");
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
