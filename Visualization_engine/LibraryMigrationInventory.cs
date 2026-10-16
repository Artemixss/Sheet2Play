using System.Diagnostics;
using System.Text.Json;

namespace SynthesiaClone;

internal static class LibraryMigrationInventory
{
    internal static void Freeze(string destination)
    {
        if (File.Exists(destination)) throw new IOException("Inventory already exists; use resume.");
        string library = SongCache.ApplicationDirectory;
        string bridge = Path.Combine(AppContext.BaseDirectory, "Bridge", "bridge.py");
        string helper = Path.Combine(AppContext.BaseDirectory, "Bridge", "library_inventory.py");
        ProcessStartInfo startInfo = new(OmrPipeline.ResolveEnginePythonExecutable(bridge, OmrEngine.Homr465))
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        startInfo.ArgumentList.Add("-B");
        startInfo.ArgumentList.Add(helper);
        startInfo.ArgumentList.Add(library);
        using Process process = Process.Start(startInfo) ?? throw new IOException("Inventory helper did not start.");
        Task<string> stdout = process.StandardOutput.ReadToEndAsync();
        Task<string> stderr = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(300_000))
        {
            process.Kill(entireProcessTree: true);
            process.WaitForExit();
            throw new TimeoutException("Library inventory exceeded five minutes.");
        }
        if (process.ExitCode != 0) throw new InvalidDataException(stderr.GetAwaiter().GetResult());
        IReadOnlyList<MigrationItem> items = JsonSerializer.Deserialize<List<MigrationItem>>(
            stdout.GetAwaiter().GetResult(), LibraryMigrationState.JsonOptions)
            ?? throw new InvalidDataException("Inventory helper returned no items.");
        MigrationInventory inventory = new(1, library, OmrPipeline.Homr465ProfileSha256,
            LibraryMigrationState.Hash(helper), OmrPipeline.Homr465EngineRevision,
            OmrPipeline.Homr465ModelRevision, DateTimeOffset.UtcNow, items);
        Validate(inventory, library);
        foreach (MigrationItem item in items) VerifyInput(inventory, item);
        LibraryMigrationState.Write(destination, inventory, overwrite: false);
        Console.WriteLine($"Inventory frozen: {items.Count} records; {items.Count(i => i.SourceRelativePath is not null)} recoverable; " +
                          $"{items.Sum(i => i.Pages)} pages; {items.Count(i => i.SourceRelativePath is null)} unavailable.");
    }

    internal static void Validate(MigrationInventory inventory, string library)
    {
        if (inventory.Version != 1 || !string.Equals(Path.GetFullPath(inventory.Library), Path.GetFullPath(library),
                StringComparison.OrdinalIgnoreCase) || inventory.ProfileSha256 != OmrPipeline.Homr465ProfileSha256 ||
            inventory.EngineRevision != OmrPipeline.Homr465EngineRevision || inventory.ModelRevision != OmrPipeline.Homr465ModelRevision ||
            inventory.Items.Count == 0 || inventory.Items.Select(i => i.Id).Distinct().Count() != inventory.Items.Count)
            throw new InvalidDataException("Inventory library/profile/version or item identities do not match.");
        foreach (MigrationItem item in inventory.Items)
        {
            if (!IsHash(item.Id) || !IsHash(item.OldManifestSha256) || !IsHash(item.SourceSha256) ||
                (item.OldMidiSha256 is not null && !IsHash(item.OldMidiSha256)) ||
                !item.OldManifest.Replace('\\', '/').StartsWith("songs/midi/homr/", StringComparison.Ordinal) ||
                !item.OldManifest.EndsWith(".mid.cache.json", StringComparison.Ordinal) ||
                (item.SourceRelativePath is null ? item.Pages != 0 || string.IsNullOrWhiteSpace(item.UnavailableReason)
                    : item.Pages <= 0 || item.UnavailableReason is not null ||
                      !item.SourceRelativePath.Replace('\\', '/').StartsWith("songs/pdf/", StringComparison.Ordinal)))
                throw new InvalidDataException("Invalid frozen inventory item.");
            LibraryMigrationState.LibraryPath(library, item.OldManifest);
            if (item.SourceRelativePath is not null) LibraryMigrationState.LibraryPath(library, item.SourceRelativePath);
        }
    }

    internal static void VerifyInput(MigrationInventory inventory, MigrationItem item)
    {
        string manifest = LibraryMigrationState.LibraryPath(inventory.Library, item.OldManifest);
        LibraryMigrationState.VerifyHash(manifest, item.OldManifestSha256);
        LibraryMigrationState.VerifyHash(manifest[..^".cache.json".Length], item.OldMidiSha256);
        if (item.SourceRelativePath is not null)
            LibraryMigrationState.VerifyHash(LibraryMigrationState.LibraryPath(inventory.Library, item.SourceRelativePath), item.SourceSha256);
    }

    private static bool IsHash(string value) => value.Length == 64 && value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');
}
