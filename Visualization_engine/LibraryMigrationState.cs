using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

internal sealed record MigrationItem(string Id, string OldManifest, string OldManifestSha256,
    string? OldMidiSha256, string? SourceRelativePath, string SourceSha256, int Pages,
    string? UnavailableReason);

internal sealed record MigrationInventory(int Version, string Library, string ProfileSha256,
    string HelperSha256, string EngineRevision, string ModelRevision, DateTimeOffset CreatedUtc,
    IReadOnlyList<MigrationItem> Items);

internal sealed record MigrationSuccess(string Manifest, string ManifestSha256, string MidiSha256,
    int NoteCount, bool ReusedCache, double ElapsedSeconds);

internal sealed record MigrationEntry(string Id, string Status, MigrationSuccess? Success = null,
    string? Error = null, string? ErrorCode = null);

internal sealed record MigrationJournal(int Version, string InventorySha256, string ProfileSha256,
    string ExecutableSha256, DateTimeOffset UpdatedUtc, IReadOnlyList<MigrationEntry> Entries);

internal static class LibraryMigrationState
{
    internal static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters = { new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase) }
    };

    internal static string Hash(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }

    internal static T Read<T>(string path) =>
        JsonSerializer.Deserialize<T>(File.ReadAllText(path), JsonOptions)
        ?? throw new InvalidDataException("Migration document is null.");

    internal static void Write<T>(string path, T value, bool overwrite)
    {
        path = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string temporary = path + $".{Guid.NewGuid():N}.tmp";
        try
        {
            using (FileStream stream = new(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                JsonSerializer.Serialize(stream, value, JsonOptions);
                stream.Flush(flushToDisk: true);
            }
            File.Move(temporary, path, overwrite);
        }
        finally
        {
            if (File.Exists(temporary)) File.Delete(temporary);
        }
    }

    internal static string LibraryPath(string library, string relative)
    {
        string root = Path.GetFullPath(library).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (Path.IsPathRooted(relative)) throw new InvalidDataException("Expected a relative library path.");
        string path = Path.GetFullPath(Path.Combine(root, relative));
        if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Migration path escapes the library.");
        for (string? ancestor = path; ancestor is not null; ancestor = Path.GetDirectoryName(ancestor))
        {
            if ((File.Exists(ancestor) || Directory.Exists(ancestor)) &&
                (File.GetAttributes(ancestor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Migration paths cannot use redirected filesystem entries.");
            if (string.Equals(ancestor.TrimEnd(Path.DirectorySeparatorChar), root.TrimEnd(Path.DirectorySeparatorChar),
                    StringComparison.OrdinalIgnoreCase)) break;
        }
        return path;
    }

    internal static void VerifyHash(string path, string? expected)
    {
        if (expected is null ? File.Exists(path) : !File.Exists(path) || Hash(path) != expected)
            throw new InvalidDataException("A frozen library or cache identity changed.");
    }
}
