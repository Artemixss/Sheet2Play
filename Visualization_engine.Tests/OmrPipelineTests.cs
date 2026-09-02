using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class OmrPipelineTests
{
    [Fact]
    public async Task RunAsyncDeserializeszeusAndPassesEngineSelection()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("score.png", "image");
        string bridgePath = temporary.CreateFile(
            "fake_zeus_bridge.py",
            """
            import json
            import sys

            engine = sys.argv[sys.argv.index("--engine") + 1]
            print(json.dumps({
                "schema_version": 2,
                "engine": engine,
                "engine_revision": "df0d842596ccd199882ff958e628d59327ca6cba",
                "tempo_changes": [{"start_beat": 0.0, "bpm": 120.0}],
                "notes": [{
                    "pitch": "C4", "midi_pitch": 60, "start_beat": 0.0,
                    "duration_beats": 1.0, "start_seconds": 0.0,
                    "duration_seconds": 0.5, "part_index": 0,
                    "staff_index": 0, "voice_identifier": "1"
                }]
            }, separators=(",", ":")))
            """);

        OmrResult result = await OmrPipeline.RunAsync(
            inputPath,
            OmrEngine.Zeus,
            bridgePath,
            pythonExecutable: "python",
            timeout: TimeSpan.FromSeconds(10));

        Assert.Equal(OmrEngine.Zeus, result.Engine);
        Assert.Equal(OmrPipeline.ZeusEngineRevision, result.EngineRevision);
        Assert.Equal("zeus", OmrPipeline.GetEngineName(result.Engine));
    }

    [Fact]
    public void zeusRuntimeResolvesOnlyFromResearchEnvironment()
    {
        using TemporaryDirectory temporary = new();
        string bridgeDirectory = Path.Combine(temporary.Path, "Bridge");
        string runtimeDirectory = Path.Combine(
            temporary.Path,
            "Research",
            "omr",
            ".venv",
            "Scripts");
        Directory.CreateDirectory(bridgeDirectory);
        Directory.CreateDirectory(runtimeDirectory);
        string bridgePath = Path.Combine(bridgeDirectory, "bridge.py");
        string pythonPath = Path.Combine(runtimeDirectory, "python.exe");
        File.WriteAllText(bridgePath, string.Empty);
        File.WriteAllText(pythonPath, string.Empty);

        string resolved = OmrPipeline.ResolveEnginePythonExecutable(
            bridgePath,
            OmrEngine.Zeus);

        Assert.Equal(Path.GetFullPath(pythonPath), Path.GetFullPath(resolved));
        Assert.DoesNotContain("Bridge\\.venv", resolved, StringComparison.OrdinalIgnoreCase);
        Assert.Equal(
            "Run Research/omr/setup_research.ps1 -Profile Inference first.",
            OmrPipeline.GetRuntimeSetupInstruction(OmrEngine.Zeus));
    }

    [Fact]
    public async Task RunAsyncDeserializesVersionedResultAndPassesEngineSelection()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("score.png", "image");
        string bridgePath = temporary.CreateFile(
            "fake_bridge.py",
            """
            import json
            import sys

            engine = sys.argv[sys.argv.index("--engine") + 1]
            revisions = {"homr": "__HOMR_REVISION__"}
            print(json.dumps({
                "schema_version": 2,
                "engine": engine,
                "engine_revision": revisions[engine],
                "tempo_changes": [{"start_beat": 0.0, "bpm": 120.0}],
                "notes": [{
                    "pitch": "C4",
                    "midi_pitch": 60,
                    "start_beat": 0.0,
                    "duration_beats": 1.0,
                    "start_seconds": 0.0,
                    "duration_seconds": 0.5,
                    "part_index": 0,
                    "staff_index": 0,
                    "voice_identifier": "1",
                }],
            }, separators=(",", ":")))
            """.Replace("__HOMR_REVISION__", OmrPipeline.HomrEngineRevision));

        OmrResult result = await OmrPipeline.RunAsync(
            inputPath,
            OmrEngine.Homr,
            bridgePath,
            pythonExecutable: "python",
            timeout: TimeSpan.FromSeconds(10));

        Assert.Equal(OmrEngine.Homr, result.Engine);
        Assert.Single(result.TempoChanges);
        MusicNote note = Assert.Single(result.Notes);
        Assert.Equal(60, note.MidiPitch);
        Assert.Equal(0.5, note.DurationSeconds, precision: 9);
    }

    [Fact]
    public async Task RunAsyncCancellationTerminatesBridgeProcess()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("score.png", "image");
        string bridgePath = temporary.CreateFile(
            "slow_bridge.py",
            """
            import time
            time.sleep(30)
            """);
        using CancellationTokenSource cancellation = new(TimeSpan.FromMilliseconds(250));

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() =>
            OmrPipeline.RunAsync(
                inputPath,
                OmrEngine.Homr,
                bridgePath,
                pythonExecutable: "python",
                timeout: TimeSpan.FromSeconds(10),
                cancellationToken: cancellation.Token));
    }


    [Fact]
    public async Task RunAsyncParsesStructuredBridgeFailure()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("score.png", "image");
        string bridgePath = temporary.CreateFile(
            "error_bridge.py",
            """
            import sys
            print('diagnostic line', file=sys.stderr)
            print('SHEET2PLAY_ERROR:{"code":"MUSICXML_PARSE_FAILED","stage":"musicxml_validation","message":"bad MusicXML","page":2}', file=sys.stderr)
            raise SystemExit(6)
            """);

        OmrPipelineException exception = await Assert.ThrowsAsync<OmrPipelineException>(() =>
            OmrPipeline.RunAsync(
                inputPath,
                OmrEngine.Homr,
                bridgePath,
                pythonExecutable: "python",
                timeout: TimeSpan.FromSeconds(10)));

        Assert.Equal("MUSICXML_PARSE_FAILED", exception.ErrorCode);
        Assert.Equal("musicxml_validation", exception.Stage);
        Assert.Equal(6, exception.ExitCode);
        Assert.Equal(2, exception.Page);
        Assert.Contains("bad MusicXML", exception.Message);
        Assert.DoesNotContain("diagnostic line", exception.Message);
        Assert.Contains("diagnostic line", exception.StandardError);
        Assert.Contains("SHEET2PLAY_ERROR:", exception.StandardError);
    }

    [Fact]
    public async Task RunAsyncStreamsStructuredProgressBeforeSuccess()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("score.png", "image");
        string bridgePath = temporary.CreateFile(
            "progress_bridge.py",
            """
            import json
            import sys

            print('SHEET2PLAY_PROGRESS:{"schema_version":1,"engine":"homr","stage":"page_inference","status":"completed","message":"Completed page 1 of 2","page":1,"page_count":2,"completed_pages":1,"page_duration_seconds":12.5}', file=sys.stderr, flush=True)
            print(json.dumps({
                "schema_version": 2,
                "engine": "homr",
                "engine_revision": "__HOMR_REVISION__",
                "tempo_changes": [{"start_beat": 0.0, "bpm": 120.0}],
                "notes": [{
                    "pitch": "C4", "midi_pitch": 60, "start_beat": 0.0,
                    "duration_beats": 1.0, "start_seconds": 0.0,
                    "duration_seconds": 0.5, "part_index": 0,
                    "staff_index": 0, "voice_identifier": "1"
                }]
            }, separators=(",", ":")))
            """.Replace("__HOMR_REVISION__", OmrPipeline.HomrEngineRevision));
        LoadProgressTracker progress = new();

        await OmrPipeline.RunAsync(
            inputPath,
            OmrEngine.Homr,
            bridgePath,
            pythonExecutable: "python",
            timeout: TimeSpan.FromSeconds(10),
            progress: progress);

        Assert.True(progress.TryTake(out OmrProgress? update));
        Assert.NotNull(update);
        Assert.Equal(OmrProgressStages.PageInference, update.Stage);
        Assert.Equal(1, update.Page);
        Assert.Equal(2, update.PageCount);
        Assert.Equal(12.5, update.PageDurationSeconds);
    }

    [Fact]
    public void MalformedProgressRecordIsIgnored()
    {
        Assert.Null(OmrPipeline.ParseProgress("SHEET2PLAY_PROGRESS:{broken"));
        Assert.Null(OmrPipeline.ParseProgress("ordinary diagnostic"));
    }

    [Fact]
    public void zeusGrammarRetryProgressPreservesDecoderMessage()
    {
        OmrProgress? progress = OmrPipeline.ParseProgress(
            "SHEET2PLAY_PROGRESS:{\"schema_version\":1,\"engine\":\"zeus\"," +
            "\"stage\":\"page_inference\",\"status\":\"started\"," +
            "\"message\":\"Beam output invalid—retrying page 2 with grammar decoding\"," +
            "\"page\":2,\"page_count\":4,\"completed_pages\":1}");

        Assert.NotNull(progress);
        Assert.Equal(OmrEngine.Zeus, progress.Engine);
        Assert.Equal(2, progress.Page);
        Assert.Contains("grammar decoding", progress.Message);
    }
}
