using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class FrontendProgressTests
{
    [Fact]
    public void PageProgressUsesStepwiseFractionAndEwmaEta()
    {
        LoadProgressModel model = new();
        model.Start("score.pdf", OmrEngine.Homr);
        model.Apply(new OmrProgress
        {
            Engine = OmrEngine.Homr,
            Stage = OmrProgressStages.PageInference,
            Status = OmrProgressStatuses.Completed,
            Message = "page 1",
            Page = 1,
            PageCount = 4,
            CompletedPages = 1,
            PageDurationSeconds = 100
        });

        Assert.Equal(0.30, model.Fraction, precision: 9);
        Assert.Equal(300, model.EstimatedRemainingSeconds!.Value, precision: 6);

        model.Apply(new OmrProgress
        {
            Engine = OmrEngine.Homr,
            Stage = OmrProgressStages.RhythmExtraction,
            Status = OmrProgressStatuses.Started,
            Message = "rhythm",
            Page = 2,
            PageCount = 4,
            CompletedPages = 1
        });

        Assert.Equal(0.30, model.Fraction, precision: 9);
        Assert.NotNull(model.EstimatedRemainingSeconds);

        model.Apply(new OmrProgress
        {
            Engine = OmrEngine.Homr,
            Stage = OmrProgressStages.PageInference,
            Status = OmrProgressStatuses.Completed,
            Message = "page 2",
            Page = 2,
            PageCount = 4,
            CompletedPages = 2,
            PageDurationSeconds = 200
        });

        Assert.Equal(0.50, model.Fraction, precision: 9);
        Assert.Equal(250, model.EstimatedRemainingSeconds!.Value, precision: 6);
    }

    [Fact]
    public void ProductionHomrFailuresAreNotRemembered()
    {
        using TemporaryDirectory temporary = new();
        string storePath = Path.Combine(temporary.Path, "failed-omr.json");
        OmrPipelineException failure = new(
            "invalid MusicXML",
            errorCode: "MUSICXML_PARSE_FAILED",
            stage: "musicxml_validation",
            page: 1);
        OmrFailureStore.Remember("source-a", OmrEngine.Homr, failure, storePath);

        Assert.False(OmrFailureStore.TryGet(
            "source-a", OmrEngine.Homr, out _, storePath));
    }

    [Fact]
    public void DeterministiczeusFailuresAreRememberedAndRuntimeFailuresAreNot()
    {
        using TemporaryDirectory temporary = new();
        string storePath = Path.Combine(temporary.Path, "failed-omr.json");
        OmrPipelineException deterministic = new(
            "invalid Kern fields",
            errorCode: "KERN_INVALID",
            stage: "kern_validation",
            page: 2);
        OmrFailureStore.Remember(
            "source-zeus",
            OmrEngine.Zeus,
            deterministic,
            storePath);

        Assert.True(OmrFailureStore.TryGet(
            "source-zeus",
            OmrEngine.Zeus,
            out OmrFailureEntry? remembered,
            storePath));
        Assert.NotNull(remembered);
        Assert.Equal(2, remembered.Page);
        Assert.Equal(OmrPipeline.ZeusModelRevision, remembered.ModelRevision);

        OmrFailureStore.Remember(
            "source-oom",
            OmrEngine.Zeus,
            new OmrPipelineException(
                "out of memory",
                errorCode: "CUDA_OUT_OF_MEMORY",
                stage: "inference"),
            storePath);
        OmrFailureStore.Remember(
            "source-filesystem",
            OmrEngine.Zeus,
            new OmrPipelineException(
                "write failed",
                errorCode: "NORMALIZATION_FAILED",
                stage: "output_write"),
            storePath);

        Assert.False(OmrFailureStore.TryGet(
            "source-oom", OmrEngine.Zeus, out _, storePath));
        Assert.False(OmrFailureStore.TryGet(
            "source-filesystem", OmrEngine.Zeus, out _, storePath));
    }

    [Fact]
    public void DeterministicFailureStoreEvictsLeastRecentlyUsedEntries()
    {
        using TemporaryDirectory temporary = new();
        string storePath = Path.Combine(temporary.Path, "failed-omr.json");
        for (int index = 0; index < 52; index++)
        {
            OmrFailureStore.Remember(
                $"source-{index:D2}",
                OmrEngine.Zeus,
                new OmrPipelineException(
                    $"invalid page {index}",
                    errorCode: "KERN_PARSE_FAILED",
                    stage: "symbolic_parse",
                    page: 1),
                storePath);
        }

        IReadOnlyList<OmrFailureEntry> entries = OmrFailureStore.ReadForTesting(storePath);
        Assert.Equal(50, entries.Count);
        Assert.Contains(entries, entry => entry.SourceSha256 == "source-51");
    }

    [Fact]
    public void zeusErrorRecoveryOffersExplicitHomrAndSameEngineRetries()
    {
        Assert.Equal(
            [
                OmrRecoveryAction.RetrySameEngine,
                OmrRecoveryAction.RetryWithHomr,
                OmrRecoveryAction.ChooseAnotherFile
            ],
            OmrRecoveryPolicy.GetActions(OmrEngine.Zeus));
        Assert.Equal(
            [
                OmrRecoveryAction.RetrySameEngine,
                OmrRecoveryAction.ChooseAnotherFile
            ],
            OmrRecoveryPolicy.GetActions(OmrEngine.Homr));
        Assert.Equal(
            "Retry Zeus anyway",
            OmrRecoveryPolicy.GetSameEngineLabel(OmrEngine.Zeus));
    }

    [Fact]
    public void LegacyOemerFailureEntriesArePurged()
    {
        using TemporaryDirectory temporary = new();
        string storePath = Path.Combine(temporary.Path, "failed-omr.json");
        File.WriteAllText(storePath, "[{\"engine\":\"oemer\"}]");

        Assert.Empty(OmrFailureStore.ReadForTesting(storePath));
        Assert.Equal("[]", File.ReadAllText(storePath).Trim());
    }

    [Fact]
    public void ResponsiveLayoutAndKeyboardRemainInsideWindow()
    {
        UiLayout minimum = UiLayout.Create(960, 540);
        UiLayout wide = UiLayout.Create(1920, 1080);
        Keyboard keyboard = new(minimum.Width, minimum.HitLineY, minimum.KeyboardHeight);

        Assert.Equal(88, keyboard.Keys.Length);
        Assert.All(keyboard.Keys, key => Assert.InRange(key.X, 0, minimum.Width));
        keyboard.Resize(wide.Width, wide.HitLineY, wide.KeyboardHeight);
        Assert.All(keyboard.Keys, key => Assert.InRange(key.X, 0, wide.Width));
        Assert.True(wide.HitLineY > minimum.HitLineY);
        Assert.True(wide.FallSpeed > minimum.FallSpeed);
    }
}
