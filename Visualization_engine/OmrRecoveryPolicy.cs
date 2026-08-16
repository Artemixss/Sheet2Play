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
        engine switch
        {
            OmrEngine.Homr =>
            [
                OmrRecoveryAction.RetrySameEngine,
                OmrRecoveryAction.ChooseAnotherFile
            ],
            OmrEngine.Zeus =>
            [
                OmrRecoveryAction.RetrySameEngine,
                OmrRecoveryAction.RetryWithHomr,
                OmrRecoveryAction.ChooseAnotherFile
            ],
            _ => throw new ArgumentOutOfRangeException(
                nameof(engine), engine, "Unknown OMR engine.")
        };

    public static string GetSameEngineLabel(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => "Retry homr",
        OmrEngine.Zeus => "Retry Zeus anyway",
        _ => throw new ArgumentOutOfRangeException(
            nameof(engine), engine, "Unknown OMR engine.")
    };
}
