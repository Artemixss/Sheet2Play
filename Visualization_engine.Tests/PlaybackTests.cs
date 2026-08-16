using Raylib_cs;
using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class PlaybackTests
{
    [Fact]
    public void ClockPauseResumeAndSeekUseImmutableMonotonicBaselines()
    {
        double now = 10;
        PlaybackClock clock = new(() => now);
        clock.Reset(2, running: true);
        now = 13;
        Assert.Equal(5, clock.Position, precision: 9);

        clock.Pause();
        now = 20;
        Assert.Equal(5, clock.Position, precision: 9);
        clock.Seek(1.25);
        clock.Resume();
        now = 22;
        Assert.Equal(3.25, clock.Position, precision: 9);
    }

    [Fact]
    public void PlaybackRateChangesPreservePositionAndScaleFutureTime()
    {
        double now = 0;
        PlaybackClock clock = new(() => now);
        clock.Reset(4, running: true);
        now = 2;
        Assert.Equal(6, clock.Position, precision: 9);

        clock.SetPlaybackRate(0.75);
        Assert.Equal(6, clock.Position, precision: 9);
        now = 6;
        Assert.Equal(9, clock.Position, precision: 9);

        Assert.Throws<ArgumentOutOfRangeException>(() => clock.SetPlaybackRate(0.049));
    }

    [Fact]
    public void PlaybackRateStepsExactlyByFiveHundredthsWithoutDrift()
    {
        double rate = PlaybackRateRules.Minimum;
        for (int index = 0; index < 39; index++)
        {
            rate = PlaybackRateRules.Step(rate, 1);
        }

        Assert.Equal(2.00, rate, precision: 9);
        Assert.Equal(2.00, PlaybackRateRules.Step(rate, 1), precision: 9);

        for (int index = 0; index < 39; index++)
        {
            rate = PlaybackRateRules.Step(rate, -1);
        }

        Assert.Equal(0.05, rate, precision: 9);
        Assert.Equal(0.05, PlaybackRateRules.Step(rate, -1), precision: 9);
    }

    [Theory]
    [InlineData("0.05", 0.05)]
    [InlineData("0,55", 0.55)]
    [InlineData("1.37x", 1.37)]
    [InlineData("2.00", 2.00)]
    public void ManualPlaybackRateAcceptsValidValues(string text, double expected)
    {
        Assert.True(PlaybackRateRules.TryParse(text, out double rate, out string? error));
        Assert.Null(error);
        Assert.Equal(expected, rate, precision: 9);
    }

    [Theory]
    [InlineData("")]
    [InlineData("0")]
    [InlineData("2.01")]
    [InlineData("1.001")]
    [InlineData("malformed")]
    [InlineData("NaN")]
    [InlineData("Infinity")]
    [InlineData("-1")]
    public void ManualPlaybackRateRejectsInvalidValues(string text)
    {
        Assert.False(PlaybackRateRules.TryParse(text, out _, out string? error));
        Assert.False(string.IsNullOrWhiteSpace(error));
    }

    [Fact]
    public void NoteExposesStablePitchClassForRendering()
    {
        Assert.Equal("A", NewNote(0, 0, 1).PitchClass);
        Assert.Equal("F#", NewNote(45, 0, 1).PitchClass);
        Assert.Equal("C", NewNote(39, 0, 1).PitchClass);
    }

    [Fact]
    public void OverlappingSamePitchNotesDoNotSendPrematureNoteOff()
    {
        double now = 0;
        FakeMidiOutput midi = new();
        PlaybackSession session = new(
        [
            NewNote(39, 0, 1),
            NewNote(39, 0.5, 1)
        ], audioOffsetSeconds: 0);
        PlaybackController controller = new(session, midi, new PlaybackClock(() => now));

        controller.Update();
        now = 0.5;
        controller.Update();
        now = 1.0;
        controller.Update();
        Assert.Single(midi.NoteOns);
        Assert.Empty(midi.NoteOffs);

        now = 1.5;
        controller.Update();
        Assert.Single(midi.NoteOffs);
    }

    [Fact]
    public void SeekRestoresSustainedNotesAndPreservesPausedState()
    {
        double now = 0;
        FakeMidiOutput midi = new();
        PlaybackController controller = new(
            new PlaybackSession([NewNote(10, 1, 10)], audioOffsetSeconds: 0),
            midi,
            new PlaybackClock(() => now));

        controller.Seek(5, resume: true);
        Assert.True(controller.IsPlaying);
        Assert.True(controller.IsKeyActive(10));
        Assert.Equal(31, Assert.Single(midi.NoteOns));

        controller.Seek(6, resume: false);
        Assert.False(controller.IsPlaying);
        Assert.False(controller.IsKeyActive(10));
    }

    [Theory]
    [InlineData(65, "01:05")]
    [InlineData(3661, "1:01:01")]
    public void TimeFormattingUsesMinuteAndHourForms(double seconds, string expected)
    {
        Assert.Equal(expected, PlaybackFormatting.FormatTime(seconds));
    }

    [Theory]
    [InlineData(50, 100, 200, 60, 0)]
    [InlineData(200, 100, 200, 60, 30)]
    [InlineData(400, 100, 200, 60, 60)]
    public void SliderMappingClampsToSongBounds(float mouseX, float x, float width, double duration, double expected)
    {
        Assert.Equal(expected, PlaybackFormatting.PositionFromSlider(mouseX, x, width, duration), precision: 9);
    }

    [Fact]
    public void VisibleRangeDoesNotScanEntireLargeScore()
    {
        Note[] notes = Enumerable.Range(0, 10_000)
            .Select(index => NewNote(index % 88, index * 0.1, 0.05))
            .ToArray();
        PlaybackSession session = new(notes, audioOffsetSeconds: 0);

        (int start, int end) = session.GetVisibleRange(500, 1, 4);

        Assert.True(start > 4_000);
        Assert.True(end - start < 100);
    }

    [Fact]
    public async Task BackgroundLoadHandoffIsThreadSafeAndTyped()
    {
        LoadResultHandoff<List<Note>> handoff = new();
        List<Note> expected = [NewNote(1, 0, 1)];
        await Task.Run(() => handoff.Complete(expected));

        Assert.True(handoff.TryTake(out LoadCompletion<List<Note>>? completion));
        Assert.Same(expected, completion!.Value);
        Assert.Null(completion.Error);
    }

    private static Note NewNote(int key, double start, double duration) =>
        new(key, start, duration, 80, Color.SkyBlue);

    private sealed class FakeMidiOutput : IMidiOutput
    {
        public List<int> NoteOns { get; } = [];
        public List<int> NoteOffs { get; } = [];

        public void NoteOn(int midiPitch, int velocity) => NoteOns.Add(midiPitch);
        public void NoteOff(int midiPitch) => NoteOffs.Add(midiPitch);
        public void AllNotesOff()
        {
        }
    }
}
