using System.Text.Json;
using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class LibraryMigrationTests
{
    private static readonly string Executable = new('e', 64);

    [Fact]
    public void ResumeSkipsCompletedScansAfterResourceStopAndAccountsFailuresAndOrphans()
    {
        using Fixture fixture = new();
        MigrationItem first = fixture.Add("first");
        MigrationItem second = fixture.Add("second");
        MigrationItem third = fixture.Add("third");
        fixture.Add("orphan", unavailable: true);
        fixture.Freeze();
        List<string> calls = [];
        bool stop = true;
        MigrationOperations operations = new(item =>
        {
            calls.Add(item.Id);
            if (item.Id == second.Id && stop) throw new OmrPipelineException("Pressure", "RESOURCE_STOP");
            if (item.Id == third.Id) throw new OmrPipelineException("No staves", "NORMALIZATION_FAILED");
            return Complete(item);
        }, (_, _) => { }, (_, _) => { });
        Assert.Throws<OmrPipelineException>(() => fixture.Resume(operations));
        MigrationJournal partial = LibraryMigrationState.Read<MigrationJournal>(fixture.Journal);
        Assert.Equal("success", partial.Entries.Single(e => e.Id == first.Id).Status);
        Assert.Equal("pending", partial.Entries.Single(e => e.Id == second.Id).Status);
        stop = false;
        MigrationJournal completed = fixture.Resume(operations);
        Assert.Equal(1, calls.Count(id => id == first.Id));
        Assert.Equal(2, calls.Count(id => id == second.Id));
        Assert.Equal(new[] { "success", "success", "failed", "unavailable" }, completed.Entries.Select(e => e.Status));
        int count = calls.Count;
        fixture.Resume(operations);
        Assert.Equal(count, calls.Count);
    }

    [Fact]
    public void ResumeRepairsRecentMappingAfterCacheCommitWithoutRepeatingRecognition()
    {
        using Fixture fixture = new();
        fixture.Add("first");
        fixture.Freeze();
        int scans = 0;
        bool interrupted = true;
        int maps = 0;
        MigrationOperations operations = new(item => { scans++; return Complete(item); }, (_, _) => { }, (_, _) =>
        {
            maps++;
            if (interrupted) throw new IOException("Interrupted recent write");
        });
        Assert.Throws<IOException>(() => fixture.Resume(operations));
        Assert.Equal("success", LibraryMigrationState.Read<MigrationJournal>(fixture.Journal).Entries[0].Status);
        interrupted = false;
        fixture.Resume(operations);
        Assert.Equal(1, scans);
        Assert.Equal(2, maps);
    }

    [Theory]
    [InlineData("MODEL_INVALID")]
    [InlineData("CUDA_UNAVAILABLE")]
    [InlineData("RESOURCE_STOP")]
    [InlineData("RUNTIME_MISSING")]
    public void IdentityAndResourceFailuresStopBeforeTheNextItem(string code)
    {
        using Fixture fixture = new();
        fixture.Add("first");
        fixture.Add("second");
        fixture.Freeze();
        int calls = 0;
        Assert.Throws<OmrPipelineException>(() => fixture.Resume(new(_ =>
        {
            calls++;
            throw new OmrPipelineException("Stop", code);
        }, (_, _) => { }, (_, _) => { })));
        Assert.Equal(1, calls);
        Assert.All(LibraryMigrationState.Read<MigrationJournal>(fixture.Journal).Entries,
            entry => Assert.Equal("pending", entry.Status));
    }

    [Fact]
    public void SourceDriftAndChangedExecutableRejectResumeBeforeRecognition()
    {
        using Fixture fixture = new();
        MigrationItem item = fixture.Add("first");
        fixture.Freeze();
        MigrationOperations operations = new(Complete, (_, _) => { }, (_, _) => { });
        fixture.Resume(operations);
        Assert.Throws<InvalidDataException>(() => LibraryMigrationRunner.Resume(fixture.Inventory, fixture.Journal,
            fixture.Library, new string('f', 64), operations, TimeSpan.FromMinutes(1)));
        File.AppendAllText(LibraryMigrationState.LibraryPath(fixture.Library, item.SourceRelativePath!), "changed");
        Assert.Throws<InvalidDataException>(() => fixture.Resume(operations));
    }

    [Fact]
    public void RecentMappingPreservesOrderTimestampsOtherEnginesAndUnmappedFailures()
    {
        using TemporaryDirectory directory = new();
        string path = Path.Combine(directory.Path, "recent.json");
        RecentSongEntry[] before =
        [
            new("songs\\midi\\homr\\success.mid.cache.json", "One", OmrEngine.Homr, DateTimeOffset.Parse("2026-10-01T00:00:00Z")),
            new("songs/midi/homr/failed.mid.cache.json", "Two", OmrEngine.Homr, DateTimeOffset.Parse("2026-10-02T00:00:00Z")),
            new("songs/midi/custom/manual.mid", "Three", OmrEngine.DirectMidi, DateTimeOffset.Parse("2026-10-03T00:00:00Z"))
        ];
        LibraryMigrationState.Write(path, before, overwrite: false);
        RecentSongsStore.MapCommittedCache("songs/midi/homr/success.mid.cache.json", "songs/midi/homr465/new.mid.cache.json", path);
        RecentSongEntry[] after = LibraryMigrationState.Read<RecentSongEntry[]>(path);
        Assert.Equal(before.Select(e => e.LastOpenedUtc), after.Select(e => e.LastOpenedUtc));
        Assert.Equal(before.Select(e => e.DisplayName), after.Select(e => e.DisplayName));
        Assert.Equal(before[1], after[1]);
        Assert.Equal(before[2], after[2]);
        Assert.Equal(OmrEngine.Homr465, after[0].Engine);
        string hash = LibraryMigrationState.Hash(path);
        RecentSongsStore.MapCommittedCache("songs/midi/homr/success.mid.cache.json", "songs/midi/homr465/new.mid.cache.json", path);
        Assert.Equal(hash, LibraryMigrationState.Hash(path));
    }

    [Fact]
    public void RecentMappingOntoAnAlreadyListed465CacheKeepsOneNewestEntry()
    {
        using TemporaryDirectory directory = new();
        string path = Path.Combine(directory.Path, "recent.json");
        RecentSongEntry[] before =
        [
            new("songs\\midi\\homr465\\new.mid.cache.json", "Opened as 465", OmrEngine.Homr465, DateTimeOffset.Parse("2026-10-01T00:00:00Z")),
            new("songs/midi/custom/manual.mid", "Other", OmrEngine.DirectMidi, DateTimeOffset.Parse("2026-10-02T00:00:00Z")),
            new("songs\\midi\\homr\\success.mid.cache.json", "Opened as 426", OmrEngine.Homr, DateTimeOffset.Parse("2026-10-03T00:00:00Z"))
        ];
        LibraryMigrationState.Write(path, before, overwrite: false);
        RecentSongsStore.MapCommittedCache("songs/midi/homr/success.mid.cache.json", "songs/midi/homr465/new.mid.cache.json", path);
        RecentSongEntry[] after = LibraryMigrationState.Read<RecentSongEntry[]>(path);
        Assert.Equal(["Other", "Opened as 426"], after.Select(e => e.DisplayName));
        Assert.Equal("songs/midi/homr465/new.mid.cache.json", after[1].ManifestRelativePath);
        Assert.Equal(OmrEngine.Homr465, after[1].Engine);
        Assert.Equal(before[2].LastOpenedUtc, after[1].LastOpenedUtc);
    }

    [Fact]
    public void RecentLoadToleratesAStoreThatAlreadyListsAManifestTwice()
    {
        using TemporaryDirectory directory = new();
        string path = Path.Combine(directory.Path, "recent.json");
        const string manifest = "songs\\midi\\homr465\\same.mid.cache.json";
        LibraryMigrationState.Write(path, new RecentSongEntry[]
        {
            new(manifest, "Newer", OmrEngine.Homr465, DateTimeOffset.Parse("2026-10-14T20:33:29Z")),
            new(manifest, "Older", OmrEngine.Homr465, DateTimeOffset.Parse("2026-10-14T20:33:16Z")),
            new("songs/midi/custom/manual.mid", "Other", OmrEngine.DirectMidi, DateTimeOffset.Parse("2026-10-13T00:00:00Z"))
        }, overwrite: false);
        string hash = LibraryMigrationState.Hash(path);
        IReadOnlyList<RecentSongEntry> entries = RecentSongsStore.Load(path);
        Assert.Equal(["Newer", "Other"], entries.Select(e => e.DisplayName));
        Assert.Equal(hash, LibraryMigrationState.Hash(path));
    }

    [Fact]
    public void MigrationPathsRejectTraversalAndAbsolutePaths()
    {
        using TemporaryDirectory directory = new();
        Assert.Throws<InvalidDataException>(() => LibraryMigrationState.LibraryPath(directory.Path, "../outside"));
        Assert.Throws<InvalidDataException>(() => LibraryMigrationState.LibraryPath(directory.Path, directory.Path));
    }

    private static MigrationSuccess Complete(MigrationItem item) => new("songs/midi/homr465/new.mid.cache.json",
        new string('a', 64), new string('b', 64), 1, false, 0.1);

    private sealed class Fixture : IDisposable
    {
        private readonly TemporaryDirectory directory = new();
        private readonly List<MigrationItem> items = [];
        internal string Library => directory.Path;
        internal string Inventory => Path.Combine(directory.Path, "inventory.json");
        internal string Journal => Path.Combine(directory.Path, "journal.json");

        internal MigrationItem Add(string name, bool unavailable = false)
        {
            string old = $"songs/midi/homr/{name}.mid.cache.json";
            string manifest = Path.Combine(Library, old);
            Directory.CreateDirectory(Path.GetDirectoryName(manifest)!);
            File.WriteAllText(manifest, name);
            string? source = unavailable ? null : $"songs/pdf/{name}.png";
            if (source is not null)
            {
                Directory.CreateDirectory(Path.Combine(Library, "songs/pdf"));
                File.WriteAllText(Path.Combine(Library, source), name);
            }
            MigrationItem item = new(LibraryMigrationState.Hash(manifest), old, LibraryMigrationState.Hash(manifest), null,
                source, source is null ? new string('c', 64) : LibraryMigrationState.Hash(Path.Combine(Library, source)),
                unavailable ? 0 : 1, unavailable ? "No retained source or MIDI" : null);
            items.Add(item);
            return item;
        }

        internal void Freeze() => LibraryMigrationState.Write(Inventory, new MigrationInventory(1, Library,
            OmrPipeline.Homr465ProfileSha256, new string('d', 64), OmrPipeline.Homr465EngineRevision,
            OmrPipeline.Homr465ModelRevision, DateTimeOffset.UtcNow, items), overwrite: false);

        internal MigrationJournal Resume(MigrationOperations operations) => LibraryMigrationRunner.Resume(
            Inventory, Journal, Library, Executable, operations, TimeSpan.FromMinutes(1));

        public void Dispose() => directory.Dispose();
    }
}
