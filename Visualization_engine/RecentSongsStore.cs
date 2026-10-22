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
    // Songs were once named with this suffix when converted with the timing fix; the setting now
    // says which conversion plays.
    private const string RetiredTimingSuffix = " · timing fix";
    private static readonly object Gate = new();
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters = { new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase) }
    };

    public static string DefaultPath => Path.Combine(
        Path.GetDirectoryName(AppSettingsStore.GetSettingsPath())!,
        "recent.json");

    public static IReadOnlyList<RecentSongEntry> Load(string? storePath = null)
    {
        lock (Gate)
        {
            return KeepLatestPerSong(ReadEntries(storePath ?? DefaultPath))
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
            // Another interpretation or cache of the same song is replaced, not listed beside it.
            string song = SongKey(entry.ManifestRelativePath);
            entries.RemoveAll(item => string.Equals(SongKey(item.ManifestRelativePath), song, StringComparison.OrdinalIgnoreCase));
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
            return WithoutRetiredSuffix(JsonSerializer.Deserialize<List<RecentSongEntry>>(
                       File.ReadAllText(path), JsonOptions) ?? []);
        }
        catch (JsonException)
        {
            return WithoutRetiredSuffix(MigrateLegacyEntries(path));
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

    internal static void MapCommittedCache(string oldManifest, string newManifest, string? storePath = null)
    {
        string path = storePath ?? DefaultPath;
        lock (Gate)
        {
            if (!File.Exists(path)) return;
            List<RecentSongEntry> entries = JsonSerializer.Deserialize<List<RecentSongEntry>>(
                File.ReadAllText(path), JsonOptions) ?? throw new InvalidDataException("Recent-song store is null.");
            bool changed = false;
            for (int index = 0; index < entries.Count; index++)
            {
                RecentSongEntry entry = entries[index];
                if (entry.Engine != OmrEngine.Homr || !string.Equals(entry.ManifestRelativePath.Replace('\\', '/'),
                        oldManifest.Replace('\\', '/'), StringComparison.OrdinalIgnoreCase)) continue;
                entries[index] = entry with { ManifestRelativePath = newManifest, Engine = OmrEngine.Homr465 };
                changed = true;
            }
            // The 465 cache may already be in the list from opening it directly; mapping the
            // 426 entry onto it must not leave the same manifest listed twice.
            if (changed) WriteEntries(path, KeepLatestPerSong(entries), throwOnFailure: true);
        }
    }

    /// <summary>
    /// What identifies a song across its files: a package folder for any of its interpretations, or
    /// a MIDI cache's name without its <c>.timing-</c> part. Anything else is its own path.
    /// </summary>
    internal static string SongKey(string manifestRelativePath)
    {
        const string CacheSuffix = ".mid.cache.json";
        string path = manifestRelativePath.Replace('\\', '/');
        string[] parts = path.Split('/');
        if (parts.Length > 3 && parts[^3].Equals("derived", StringComparison.OrdinalIgnoreCase) &&
            parts[^1].Equals("interpretation.json", StringComparison.OrdinalIgnoreCase))
        {
            return string.Join('/', parts[..^3]);
        }
        if (path.EndsWith(CacheSuffix, StringComparison.OrdinalIgnoreCase))
        {
            string stem = path[..^CacheSuffix.Length];
            int timing = stem.IndexOf(".timing-", stem.LastIndexOf('/') + 1, StringComparison.Ordinal);
            return (timing >= 0 ? stem[..timing] : stem) + CacheSuffix;
        }
        return path;
    }

    private static List<RecentSongEntry> WithoutRetiredSuffix(List<RecentSongEntry> entries) =>
        entries.Select(static entry => entry.DisplayName.EndsWith(RetiredTimingSuffix, StringComparison.Ordinal)
                ? entry with { DisplayName = entry.DisplayName[..^RetiredTimingSuffix.Length] }
                : entry)
            .ToList();

    private static List<RecentSongEntry> KeepLatestPerSong(List<RecentSongEntry> entries)
    {
        Dictionary<string, int> latest = new(StringComparer.OrdinalIgnoreCase);
        for (int index = 0; index < entries.Count; index++)
        {
            string key = SongKey(entries[index].ManifestRelativePath);
            if (!latest.TryGetValue(key, out int kept) ||
                entries[index].LastOpenedUtc > entries[kept].LastOpenedUtc)
            {
                latest[key] = index;
            }
        }
        HashSet<int> retained = [.. latest.Values];
        return entries.Where((_, index) => retained.Contains(index)).ToList();
    }

    private static void WriteEntries(string path, IReadOnlyCollection<RecentSongEntry> entries, bool throwOnFailure = false)
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
            if (throwOnFailure) throw;
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
