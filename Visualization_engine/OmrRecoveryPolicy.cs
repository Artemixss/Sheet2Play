namespace SynthesiaClone;

internal enum OmrRecoveryAction
{
    RetrySameEngine,
    RetryWithHomr,
    ChooseAnotherFile
}

internal static class OmrRecoveryPolicy
{
    public static IReadOnlyList<OmrRecoveryAction> GetActions(OmrEngine engine) =>
        OmrEngines.RunsOmr(engine)
            ?
            [
                OmrRecoveryAction.RetrySameEngine,
                OmrRecoveryAction.RetryWithHomr,
                OmrRecoveryAction.ChooseAnotherFile
            ]
            : throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.");

    public static string GetSameEngineLabel(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => "Retry homr",
        OmrEngine.Homr465 => "Retry HOMR 465",
        OmrEngine.Homr480 => "Retry HOMR 480",
        OmrEngine.Zeus => "Retry Zeus anyway",
        _ => throw new ArgumentOutOfRangeException(
            nameof(engine), engine, "Unknown OMR engine.")
    };

    /// <summary>
    /// The engine the error screen offers instead, always one the home screen offers: HOMR 480, the
    /// default, falls back to the secondary HOMR 465, and every other engine to HOMR 480.
    /// </summary>
    public static OmrEngine GetAlternateEngine(OmrEngine engine) =>
        engine == OmrEngine.Homr480 ? OmrEngine.Homr465 : OmrEngine.Homr480;

    public static string GetAlternateLabel(OmrEngine engine) => GetAlternateEngine(engine) switch
    {
        OmrEngine.Homr465 => "Retry HOMR 465",
        _ => "Retry HOMR 480"
    };
}
