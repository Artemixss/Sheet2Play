using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

public static class OmrProgressStages
{
    public const string CacheLookup = "cache_lookup";
    public const string InputInspection = "input_inspection";
    public const string ModelLoad = "model_load";
    public const string PageInference = "page_inference";
    public const string GpuSegmentation = "gpu_segmentation";
    public const string SymbolExtraction = "symbol_extraction";
    public const string RhythmExtraction = "rhythm_extraction";
    public const string MusicXmlExport = "musicxml_export";
    public const string Normalization = "normalization";
    public const string MidiWrite = "midi_write";
    public const string CacheValidation = "cache_validation";
    public const string Complete = "complete";
    public const string KnownFailure = "known_failure";
}

public static class OmrProgressStatuses
{
    public const string Started = "started";
    public const string Completed = "completed";
}

public sealed record OmrProgress
{
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; init; } = 1;

    [JsonPropertyName("engine")]
    public OmrEngine Engine { get; init; }

    [JsonPropertyName("stage")]
    public string Stage { get; init; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("message")]
    public string Message { get; init; } = string.Empty;

    [JsonPropertyName("page")]
    public int? Page { get; init; }

    [JsonPropertyName("page_count")]
    public int? PageCount { get; init; }

    [JsonPropertyName("completed_pages")]
    public int? CompletedPages { get; init; }

    [JsonPropertyName("elapsed_seconds")]
    public double? ElapsedSeconds { get; init; }

    [JsonPropertyName("page_duration_seconds")]
    public double? PageDurationSeconds { get; init; }

    [JsonPropertyName("token_count")]
    public int? TokenCount { get; init; }
}

public sealed class LoadProgressTracker : IProgress<OmrProgress>
{
    private readonly ConcurrentQueue<OmrProgress> pending = new();

    public void Report(OmrProgress value)
    {
        ArgumentNullException.ThrowIfNull(value);
        pending.Enqueue(value);
    }

    public bool TryTake(out OmrProgress? progress) => pending.TryDequeue(out progress);
}

public sealed class LoadProgressModel
{
    private readonly Stopwatch elapsed = new();
    private double? estimatedPageSeconds;
    private double currentPageStartedAt;
    private int? activePage;

    public OmrProgress? Latest { get; private set; }
    public string FileName { get; private set; } = string.Empty;
    public OmrEngine Engine { get; private set; }
    public double ElapsedSeconds => elapsed.Elapsed.TotalSeconds;
    public bool IsRunning => elapsed.IsRunning;

    public void Start(string inputPath, OmrEngine engine)
    {
        FileName = Path.GetFileName(inputPath);
        Engine = engine;
        Latest = new OmrProgress
        {
            Engine = engine,
            Stage = OmrProgressStages.CacheLookup,
            Status = OmrProgressStatuses.Started,
            Message = "Checking song cache"
        };
        estimatedPageSeconds = null;
        currentPageStartedAt = 0;
        activePage = null;
        elapsed.Restart();
    }

    public void Apply(OmrProgress progress)
    {
        ArgumentNullException.ThrowIfNull(progress);
        Latest = progress;
        if (progress.Stage == OmrProgressStages.PageInference &&
            progress.Status == OmrProgressStatuses.Started &&
            progress.Page != activePage)
        {
            currentPageStartedAt = ElapsedSeconds;
            activePage = progress.Page;
        }
        if (progress.Stage == OmrProgressStages.PageInference &&
            progress.Status == OmrProgressStatuses.Completed &&
            progress.PageDurationSeconds is > 0 and double pageDuration)
        {
            estimatedPageSeconds = estimatedPageSeconds is null
                ? pageDuration
                : estimatedPageSeconds.Value * 0.75 + pageDuration * 0.25;
        }
        if (progress.Stage == OmrProgressStages.Complete)
        {
            elapsed.Stop();
        }
    }

    public void Stop() => elapsed.Stop();

    public double Fraction
    {
        get
        {
            if (Latest is null)
            {
                return 0;
            }
            return Latest.Stage switch
            {
                OmrProgressStages.CacheLookup => Latest.Status == OmrProgressStatuses.Completed ? 0.02 : 0,
                OmrProgressStages.InputInspection => 0.05,
                OmrProgressStages.ModelLoad => Latest.Status == OmrProgressStatuses.Completed ? 0.10 : 0.06,
                OmrProgressStages.PageInference or
                OmrProgressStages.GpuSegmentation or
                OmrProgressStages.SymbolExtraction or
                OmrProgressStages.RhythmExtraction or
                OmrProgressStages.MusicXmlExport => PageFraction(Latest),
                OmrProgressStages.Normalization => Latest.Status == OmrProgressStatuses.Completed ? 0.95 : 0.90,
                OmrProgressStages.MidiWrite => Latest.Status == OmrProgressStatuses.Completed ? 0.975 : 0.95,
                OmrProgressStages.CacheValidation => Latest.Status == OmrProgressStatuses.Completed ? 0.995 : 0.975,
                OmrProgressStages.Complete => 1,
                OmrProgressStages.KnownFailure => 0,
                _ => 0.02
            };
        }
    }

    public double? EstimatedRemainingSeconds
    {
        get
        {
            if (Latest is null || estimatedPageSeconds is null ||
                !IsActivePageStage(Latest.Stage) ||
                Latest.PageCount is not > 0)
            {
                return null;
            }

            int completed = Math.Clamp(Latest.CompletedPages ?? 0, 0, Latest.PageCount.Value);
            if (Latest.Status == OmrProgressStatuses.Started && Latest.Page is > 0)
            {
                double currentElapsed = Math.Max(0, ElapsedSeconds - currentPageStartedAt);
                int futurePages = Math.Max(0, Latest.PageCount.Value - Latest.Page.Value);
                return Math.Max(0, estimatedPageSeconds.Value - currentElapsed) +
                       futurePages * estimatedPageSeconds.Value;
            }
            return Math.Max(0, Latest.PageCount.Value - completed) * estimatedPageSeconds.Value;
        }
    }

    private static double PageFraction(OmrProgress progress)
    {
        if (progress.PageCount is not > 0)
        {
            return 0.10;
        }
        int completed = Math.Clamp(progress.CompletedPages ?? 0, 0, progress.PageCount.Value);
        return 0.10 + 0.80 * completed / progress.PageCount.Value;
    }

    private static bool IsActivePageStage(string stage) => stage is
        OmrProgressStages.PageInference or
        OmrProgressStages.GpuSegmentation or
        OmrProgressStages.SymbolExtraction or
        OmrProgressStages.RhythmExtraction or
        OmrProgressStages.MusicXmlExport;
}
