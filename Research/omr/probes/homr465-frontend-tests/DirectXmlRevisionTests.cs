using System.Reflection;
using SynthesiaClone;
using Xunit;

public sealed class DirectXmlRevisionTests
{
    [Fact]
    public void ResearchRevisionBranchRetainsExistingEngineContracts()
    {
        Assert.Equal("direct-xml", OmrPipeline.GetEngineRevision(OmrEngine.MusicXml));
        Assert.Equal(OmrPipeline.HomrEngineRevision, OmrPipeline.GetEngineRevision(OmrEngine.Homr));
        Assert.Equal(OmrPipeline.ZeusEngineRevision, OmrPipeline.GetEngineRevision(OmrEngine.Zeus));
        Assert.Throws<ArgumentOutOfRangeException>(() => OmrPipeline.GetEngineRevision((OmrEngine)999));
    }

    [Theory]
    [InlineData("direct-xml", 2, true)]
    [InlineData("unrecognized", 2, false)]
    [InlineData("direct-xml", 1, false)]
    public void DirectXmlValidationAcceptsOnlyTheSupportedContract(string revision, int schema, bool valid)
    {
        OmrResult result = new()
        {
            SchemaVersion = schema, Engine = OmrEngine.MusicXml, EngineRevision = revision,
            TempoChanges = [new() { StartBeat = 0, Bpm = 120 }],
            Notes = [new() { Pitch = "C4", MidiPitch = 60, StartBeat = 0, DurationBeats = 1,
                StartSeconds = 0, DurationSeconds = 0.5, VoiceIdentifier = "1" }]
        };
        MethodInfo validation = typeof(OmrPipeline).GetMethod("ValidateResult", BindingFlags.Static | BindingFlags.NonPublic)!;
        Action invoke = () => validation.Invoke(null, [result, OmrEngine.MusicXml]);
        if (valid) invoke();
        else Assert.IsType<OmrPipelineException>(Assert.Throws<TargetInvocationException>(invoke).InnerException);
    }

    [Fact]
    public void ResearchRepairDoesNotClaimDefaultDirectXmlImportIsComplete()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => OmrPipeline.GetModelRevision(OmrEngine.MusicXml));
        Assert.Throws<ArgumentOutOfRangeException>(() => OmrPipeline.ResolveEnginePythonExecutable(
            Path.Combine(AppContext.BaseDirectory, "Bridge", "bridge.py"), OmrEngine.MusicXml));
    }
}
