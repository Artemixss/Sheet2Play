using System.Text.Json;
using Melanchall.DryWetMidi.Common;
using Melanchall.DryWetMidi.Core;
using Melanchall.DryWetMidi.Interaction;
using SoundFont = MeltySynth.SoundFont;
using SynthesiaClone;
using Note = SynthesiaClone.Note;

namespace Visualization_engine.Tests;

/// <summary>
/// Expressive playback: pedal, dynamics, articulations, grace notes and the repeats switch, and
/// the promise that with all of it off the app plays exactly what it played before.
/// </summary>
public sealed class ExpressionTests
{
    // --- Expression off ----------------------------------------------------------------------

    [Fact]
    public void ExpressionOffReproducesThePlainTimelineAndItsEvents()
    {
        SongPerformance performance = RichScore();
        SongPlayback plain = SongTimeline.Build(performance);
        SongPlayback off = SongTimeline.Build(performance, SongTimelineOptions.For(ExpressionOptions.None));

        Assert.Empty(off.Pedal);
        Assert.Equal(Describe(plain.Notes), Describe(off.Notes));
        Assert.Equal(new PlaybackSession(plain.Notes).Events, new PlaybackSession(off.Notes, pedal: off.Pedal).Events);
        Assert.Equal(Describe(SongTimeline.BuildNotes(performance)), Describe(off.Notes));
    }

    [Fact]
    public void ExpressionOnChangesOnlyWhatTheScoreMarks()
    {
        SongPerformance performance = RichScore();
        SongPlayback on = SongTimeline.Build(performance, SongTimelineOptions.For(new ExpressionOptions()));
        Assert.NotEmpty(on.Pedal);
        Assert.Contains(on.Notes, note => note.Velocity != 80);
        Assert.Equal(new ExpressionAvailability(true, true, true, true), SongExpression.Availability(performance));
    }

    // --- Dynamics ----------------------------------------------------------------------------

    [Fact]
    public void DynamicMarksOrderVelocitiesFromPianissimoToFortissimo()
    {
        string[] marks = ["pp", "p", "mf", "f", "ff"];
        Score score = new(measures: marks.Length);
        for (int measure = 0; measure < marks.Length; measure++)
        {
            score.Note(measure, 0, 2, 60);
            score.Dynamic(measure, 0, marks[measure]);
        }
        int[] velocities = Velocities(score.Build());
        Assert.Equal([33, 49, 80, 96, 112], velocities);
        Assert.True(velocities.Zip(velocities.Skip(1)).All(pair => pair.First < pair.Second));
    }

    [Fact]
    public void AnExportedSoundDynamicsValueIsTheLevel()
    {
        // MusicXML's <sound dynamics> is a percentage of forte, which is velocity 90.
        Score score = new(measures: 2);
        score.Note(0, 0, 2, 60);
        score.Note(1, 0, 2, 60);
        score.Dynamic(0, 0, "f", sound: 106.67);
        score.Dynamic(1, 0, null, sound: 50);
        Assert.Equal([96, 45], Velocities(score.Build()));
    }

    [Fact]
    public void ASforzandoStrikesOneChordAndAFortePianoDropsAfterIt()
    {
        Score score = new(measures: 2);
        score.Dynamic(0, 0, "p");
        score.Note(0, 0, 1, 60);
        score.Note(0, 1, 1, 62);
        score.Dynamic(0, 1, "sfz");
        score.Note(1, 0, 1, 64);
        score.Dynamic(1, 0, "fp");
        score.Note(1, 1, 1, 65);
        Assert.Equal([49, 112, 96, 49], Velocities(score.Build()));
    }

    [Fact]
    public void ACrescendoRisesSteadilyToTheDynamicItLeadsTo()
    {
        Score score = new(measures: 5);
        score.Dynamic(0, 0, "p");
        for (int measure = 0; measure < 5; measure++)
        {
            score.Note(measure, 0, 1, 60);
            score.Note(measure, 1, 1, 62);
        }
        score.Wedge("crescendo", 0, 0, 3, 2);
        score.Dynamic(4, 0, "f");
        int[] velocities = Velocities(score.Build());
        Assert.Equal(49, velocities[0]);
        Assert.Equal(96, velocities[^1]);
        Assert.True(velocities.Zip(velocities.Skip(1)).All(pair => pair.First <= pair.Second));
        Assert.True(velocities.Distinct().Count() >= 6, string.Join(",", velocities));
    }

    [Fact]
    public void ADiminuendoWithNoTargetFallsOneStepAndHolds()
    {
        Score score = new(measures: 3);
        score.Dynamic(0, 0, "f");
        for (int measure = 0; measure < 3; measure++)
        {
            score.Note(measure, 0, 1, 60);
            score.Note(measure, 1, 1, 62);
        }
        score.Wedge("diminuendo", 0, 0, 1, 2);
        int[] velocities = Velocities(score.Build());
        Assert.Equal(96, velocities[0]);
        Assert.True(velocities.Zip(velocities.Skip(1)).All(pair => pair.First >= pair.Second));
        Assert.Equal([96 - SongExpression.HairpinStep, 96 - SongExpression.HairpinStep], velocities[^2..]);
    }

    [Fact]
    public void DynamicsAreRereadOnEveryPassOfARepeat()
    {
        // A p at the start of a repeated measure and an f after it: each pass starts quiet again.
        Score score = new(measures: 2, playOrder: [0, 1, 0, 1]);
        score.Dynamic(0, 0, "p");
        score.Note(0, 0, 2, 60);
        score.Dynamic(1, 0, "f");
        score.Note(1, 0, 2, 62);
        Assert.Equal([49, 96, 49, 96], Velocities(score.Build()));
    }

    // --- Articulations and grace notes -------------------------------------------------------

    [Fact]
    public void ArticulationsShortenAndAccentNotes()
    {
        Score score = new(measures: 6);
        score.Note(0, 0, 2, 60, "staccato");
        score.Note(1, 0, 2, 60, "staccatissimo");
        score.Note(2, 0, 2, 60, "tenuto");
        score.Note(3, 0, 2, 60, "staccato", "tenuto");
        score.Note(4, 0, 2, 60, "accent");
        score.Note(5, 0, 2, 60, "strong-accent");
        List<Note> notes = SongTimeline.BuildNotes(score.Build(), SongTimelineOptions.For(new ExpressionOptions()));
        // A half note at 120 lasts one second.
        Assert.Equal([0.5, 0.25, 1.0, 0.75, 1.0, 1.0], notes.Select(note => Math.Round(note.Duration, 9)));
        Assert.Equal([80, 80, 80, 80, 96, 104], notes.Select(note => note.Velocity));
    }

    [Fact]
    public void AnArpeggiatedChordRollsUpwardAndEndsTogether()
    {
        Score score = new(measures: 1);
        score.Note(0, 0, 2, 67, "arpeggiate");
        score.Note(0, 0, 2, 60, "arpeggiate");
        score.Note(0, 0, 2, 64, "arpeggiate");
        List<Note> notes = SongTimeline.BuildNotes(score.Build(), SongTimelineOptions.For(new ExpressionOptions()));
        Assert.Equal([60, 64, 67], notes.Select(note => note.MidiPitch));
        Assert.Equal([0.0, 0.03, 0.06], notes.Select(note => Math.Round(note.StartTime, 9)));
        Assert.All(notes, note => Assert.Equal(1.0, Math.Round(note.EndTime, 9)));
    }

    [Fact]
    public void GraceNotesPlayInOrderJustBeforeTheBeat()
    {
        Score score = new(measures: 2);
        score.Note(0, 0, 2, 60);
        score.Grace(1, 0, 70, slash: false);
        score.Grace(1, 0, 71, slash: true);
        score.Note(1, 0, 2, 72);
        List<Note> notes = SongTimeline.BuildNotes(score.Build(), SongTimelineOptions.For(new ExpressionOptions()));
        Note[] graces = notes.Where(note => note.MidiPitch is 70 or 71).ToArray();
        // The principal stays on its beat (1 s); the 16th and the 32nd end on it, in written order.
        Assert.Equal(1.0, notes.Single(note => note.MidiPitch == 72).StartTime, 9);
        Assert.Equal([(70, 0.8125, 0.125), (71, 0.9375, 0.0625)],
            graces.Select(note => (note.MidiPitch, Math.Round(note.StartTime, 9), Math.Round(note.Duration, 9))));
        Assert.DoesNotContain(SongTimeline.BuildNotes(score.Build()), note => note.MidiPitch is 70 or 71);
    }

    [Fact]
    public void AGraceNoteBeforeTheFirstBeatFitsAfterTheStart()
    {
        Score score = new(measures: 1);
        score.Grace(0, 0, 70, slash: true);
        score.Note(0, 0, 2, 72);
        List<Note> notes = SongTimeline.BuildNotes(score.Build(), SongTimelineOptions.For(new ExpressionOptions()));
        Assert.Equal([72], notes.Select(note => note.MidiPitch));
    }

    // --- Pedal ---------------------------------------------------------------------------------

    [Fact]
    public void PedalMarksBecomeChangesOnEveryPass()
    {
        Score score = new(measures: 3, playOrder: [0, 1, 0, 1, 2]);
        score.Note(0, 0, 2, 60);
        score.Pedal(0, 0, "start");
        score.Pedal(0, 1, "change");
        score.Pedal(1, 1.5, "stop");
        score.Note(2, 0, 2, 60);
        score.PedalSound(2, 0, "yes");
        score.PedalSound(2, 1, "40");
        List<(double, int)> pedal = Pedal(score.Build());
        Assert.Equal([
            (0.0, 127), (0.5, 0), (0.5, 127), (1.75, 0),
            (2.0, 127), (2.5, 0), (2.5, 127), (3.75, 0),
            (4.0, 127), (4.5, 51)], pedal);
    }

    [Fact]
    public void AStopAndAStartAtOnePlaceAreAChangeInEitherOrder()
    {
        Score score = new(measures: 2);
        score.Note(0, 0, 2, 60);
        score.Pedal(0, 0, "start");
        score.Pedal(1, 0, "start");
        score.Pedal(1, 0, "stop");
        Assert.Equal([(0.0, 127), (1.0, 0), (1.0, 127)], Pedal(score.Build()));
    }

    [Fact]
    public void APedalChangeReleasesBeforeTheChordAndCatchesIt()
    {
        PlaybackSession session = new([NewNote(10, 0, 1), NewNote(12, 1, 1)], pedal:
            [new PedalChange(0, 127), new PedalChange(1, 0), new PedalChange(1, 127)]);
        string[] order = session.Events.Where(item => item.Time == 1).Select(Label).ToArray();
        Assert.Equal(["pedal 0", "off 10", "on 12", "pedal 127"], order);
    }

    [Fact]
    public void PedalStateIsRightAfterEveryOneOfAThousandRandomSeeks()
    {
        SongPlayback playback = SongTimeline.Build(RichScore(), SongTimelineOptions.For(new ExpressionOptions()));
        PlaybackSession session = new(playback.Notes, audioOffsetSeconds: 0, playback.Pedal);
        Assert.True(session.Pedal.Count >= 6);
        double now = 0;
        RecordingMidiOutput output = new();
        PlaybackController controller = new(session, output, new PlaybackClock(() => now));
        Random random = new(20261019);
        for (int trial = 0; trial < 1000; trial++)
        {
            double target = random.NextDouble() * session.TotalDuration;
            controller.Seek(target, resume: true);
            Assert.Equal(Expected(session, target), output.Sustain);

            double step = random.NextDouble() * 1.5;
            now += step;
            controller.Update();
            double position = Math.Min(target + step, session.TotalDuration);
            if (controller.IsCompleted)
            {
                Assert.Equal(0, output.Sustain);
            }
            else
            {
                Assert.Equal(Expected(session, position), output.Sustain);
            }
        }
        controller.Pause();
        Assert.Equal(0, output.Sustain);
    }

    [Fact]
    public void ASessionWithoutPedalNeverTouchesTheSustainController()
    {
        RecordingMidiOutput output = new();
        double now = 0;
        PlaybackController controller = new(new PlaybackSession([NewNote(10, 0, 1)], 0), output,
            new PlaybackClock(() => now));
        controller.Seek(0.5, resume: true);
        controller.Pause();
        Assert.Equal(0, output.SustainCalls);
    }

    [Fact]
    public void TheSynthHoldsVoicesWhileThePedalIsDownAndRendersPhaseTwoWithoutIt()
    {
        SoundFont? soundFont = InstalledSoundFont();
        if (soundFont is null)
        {
            return;
        }
        Note[] notes = [NewNote(39, 0, 0.5)];
        PlaybackSession plain = new(notes);
        PlaybackSession pedalled = new(notes, pedal: [new PedalChange(0, 127), new PedalChange(2.0, 0)]);

        (float[] plainSamples, Dictionary<double, int> plainVoices) = Render(soundFont, plain, 4.0);
        (_, Dictionary<double, int> pedalVoices) = Render(soundFont, pedalled, 4.0);
        Assert.True(pedalVoices[1.9] > 0, "the pedal holds the released note");
        Assert.Equal(0, plainVoices[1.9]);
        Assert.Equal(0, pedalVoices[3.9]);

        SongPerformance performance = RichScore();
        PlaybackSession phaseTwo = new(SongTimeline.BuildNotes(performance));
        SongPlayback off = SongTimeline.Build(performance, SongTimelineOptions.For(ExpressionOptions.None));
        PlaybackSession expressionOff = new(off.Notes, pedal: off.Pedal);
        Assert.Equal(Render(soundFont, phaseTwo, 3.0).Samples, Render(soundFont, expressionOff, 3.0).Samples);
        Assert.DoesNotContain(plainSamples, float.IsNaN);
    }

    [Fact]
    public void TheSynthRestoresThePedalAtEverySeekPoint()
    {
        SoundFont? soundFont = InstalledSoundFont();
        if (soundFont is null)
        {
            return;
        }
        SongPlayback playback = SongTimeline.Build(RichScore(), SongTimelineOptions.For(new ExpressionOptions()));
        PlaybackSession session = new(playback.Notes, pedal: playback.Pedal);
        SoundFontEngine engine = new(soundFont, new CapturingSink(), session, 48000);
        Random random = new(7);
        for (int trial = 0; trial < 1000; trial++)
        {
            double target = random.NextDouble() * session.TotalDuration;
            engine.Seek(target);
            Assert.Equal(Expected(session, target), engine.PedalValue);
        }
        engine.Start();
        engine.Stop();
        Assert.Equal(0, engine.PedalValue);
    }

    // --- MIDI files and the panel --------------------------------------------------------------

    [Fact]
    public void AMidiFilesSustainPedalIsReadAsOnePedal()
    {
        using TemporaryDirectory directory = new();
        string path = Path.Combine(directory.Path, "pedal.mid");
        MidiFile file = new(new TrackChunk(
            new ControlChangeEvent((SevenBitNumber)64, (SevenBitNumber)127) { DeltaTime = 0 },
            new NoteOnEvent((SevenBitNumber)60, (SevenBitNumber)90) { DeltaTime = 0 },
            new NoteOffEvent((SevenBitNumber)60, (SevenBitNumber)0) { DeltaTime = 480 },
            new ControlChangeEvent((SevenBitNumber)64, (SevenBitNumber)0) { DeltaTime = 480 },
            new ControlChangeEvent((SevenBitNumber)64, (SevenBitNumber)0) { DeltaTime = 10 }))
        {
            TimeDivision = new TicksPerQuarterNoteTimeDivision(480)
        };
        file.Write(path);

        List<PedalChange> pedal = SongCache.ReadMidiPedalForTesting(path);
        Assert.Equal([(0.0, 127), (1.0, 0)], pedal.Select(change => (Math.Round(change.Time, 6), change.Value)));
        SongLoadResult song = new(SongCache.ReadMidiForTesting(path), "pedal", OmrEngine.DirectMidi, true, null,
            Pedal: pedal);
        Assert.Equal(2, ExpressionPlayback.ForSong(song, new ExpressionOptions()).Pedal.Count);
        Assert.Empty(ExpressionPlayback.ForSong(song, new ExpressionOptions(Pedal: false)).Pedal);
        Assert.Equal(new ExpressionAvailability(true, false, false, false), ExpressionPlayback.Availability(song));
    }

    [Fact]
    public void TurningRepeatsOffKeepsThePlaceInTheMeasure()
    {
        Score score = new(measures: 3, playOrder: [0, 1, 0, 1, 2]);
        score.Note(0, 0, 2, 60);
        SongLoadResult song = new([], "repeat", OmrEngine.MusicXml, true, null, score.Build());
        ExpressionOptions on = new();
        ExpressionOptions off = on with { Repeats = false };
        // 3.5 s is half way through the second pass of measure 1; without repeats that is 1.5 s.
        Assert.Equal(1.5, ExpressionPlayback.MapPosition(song, on, off, 3.5), 9);
        Assert.Equal(1.5, ExpressionPlayback.MapPosition(song, off, on, 1.5), 9);
        Assert.Equal(2.5, ExpressionPlayback.MapPosition(song, on, on with { Pedal = false }, 2.5), 9);
    }

    [Fact]
    public void ExpressionSwitchesPersistAndDefaultOn()
    {
        using TemporaryDirectory directory = new();
        string settings = Path.Combine(directory.Path, "settings.json");
        Assert.Equal(new ExpressionOptions(), AppSettingsStore.LoadExpressionFromPath(settings));
        AppSettingsStore.SaveExpressionToPath(new ExpressionOptions(Dynamics: false, Repeats: false), settings);
        Assert.Equal(new ExpressionOptions(Dynamics: false, Repeats: false), AppSettingsStore.LoadExpressionFromPath(settings));
        Assert.Equal(OmrEngine.Homr480, AppSettingsStore.LoadEngineFromPath(settings));
    }

    // --- Helpers -------------------------------------------------------------------------------

    /// <summary>Repeats, pedal marks, dynamics, a hairpin, articulations, a roll and a grace note.</summary>
    private static SongPerformance RichScore()
    {
        Score score = new(measures: 6, playOrder: [0, 1, 2, 1, 2, 3, 4, 5]);
        score.Dynamic(0, 0, "p");
        score.Pedal(0, 0, "start");
        for (int measure = 0; measure < 6; measure++)
        {
            score.Note(measure, 0, 1, 48 + measure, "staccato");
            score.Note(measure, 1, 1, 60 + measure, measure % 2 == 0 ? "accent" : "tenuto");
            score.Note(measure, 0, 2, 72, "arpeggiate");
            score.Note(measure, 0, 2, 76, "arpeggiate");
            score.Pedal(measure, 1, "change");
        }
        score.Grace(3, 1, 59, slash: true);
        score.Wedge("crescendo", 1, 0, 2, 2);
        score.Dynamic(3, 0, "f");
        score.Dynamic(4, 1, "sfz");
        score.Pedal(5, 1.5, "stop");
        return score.Build();
    }

    private static int[] Velocities(SongPerformance performance) =>
        SongTimeline.BuildNotes(performance, SongTimelineOptions.For(new ExpressionOptions()))
            .Select(note => note.Velocity).ToArray();

    private static List<(double, int)> Pedal(SongPerformance performance) =>
        SongTimeline.Build(performance, SongTimelineOptions.For(new ExpressionOptions())).Pedal
            .Select(change => (Math.Round(change.Time, 9), change.Value)).ToList();

    private static string[] Describe(IEnumerable<Note> notes) =>
        notes.Select(note => $"{note.TargetKeyIndex}:{note.StartTime:R}:{note.Duration:R}:{note.Velocity}").ToArray();

    private static string Label(PlaybackEvent item) =>
        item.IsPedal ? $"pedal {item.Velocity}" : $"{(item.IsNoteOn ? "on" : "off")} {item.KeyIndex}";

    /// <summary>The pedal at a time, read straight from the session's list of changes.</summary>
    private static int Expected(PlaybackSession session, double time) =>
        session.Pedal.LastOrDefault(change => change.Time <= time).Value;

    private static Note NewNote(int key, double start, double duration) => new(key, start, duration, 80, Raylib_cs.Color.SkyBlue);

    private static SoundFont? InstalledSoundFont()
    {
        string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Sheet2Play", "soundfonts");
        string? path = Directory.Exists(folder) ? Directory.GetFiles(folder, "*.sf2").FirstOrDefault() : null;
        return path is null ? null : new SoundFont(path);
    }

    private static (float[] Samples, Dictionary<double, int> Voices) Render(SoundFont soundFont, PlaybackSession session,
        double seconds)
    {
        CapturingSink sink = new();
        SoundFontEngine engine = new(soundFont, sink, session, 48000);
        engine.Seek(0);
        engine.Start();
        Dictionary<double, int> voices = [];
        double[] probes = [1.9, 3.9];
        while (engine.SubmittedSongSeconds < seconds)
        {
            engine.RenderBlock();
            foreach (double probe in probes)
            {
                if (!voices.ContainsKey(probe) && engine.SubmittedSongSeconds >= probe)
                {
                    voices[probe] = engine.ActiveVoiceCount;
                }
            }
        }
        return (sink.Samples.ToArray(), voices);
    }

    private sealed class CapturingSink : IAudioSink
    {
        public List<float> Samples { get; } = [];
        public int BlockFrames => 1024;
        public bool WantsBlock => true;
        public void Submit(ReadOnlySpan<float> interleaved) => Samples.AddRange(interleaved.ToArray());
    }

    private sealed class RecordingMidiOutput : IMidiOutput
    {
        public int Sustain { get; private set; }
        public int SustainCalls { get; private set; }

        public void NoteOn(int midiPitch, int velocity)
        {
        }

        public void NoteOff(int midiPitch)
        {
        }

        public void AllNotesOff()
        {
        }

        public void SetSustain(int value)
        {
            Sustain = value;
            SustainCalls++;
        }
    }

    /// <summary>A one-part piano score in 2/4 at the default 120: a measure lasts one second.</summary>
    private sealed class Score(int measures, int[]? playOrder = null)
    {
        private readonly List<SongNote> notes = [];
        private readonly List<SongPedal> pedals = [];
        private readonly List<SongDynamic> dynamics = [];
        private readonly List<SongWedge> wedges = [];

        public void Note(int measure, double offset, double duration, int midi, params string[] articulations) =>
            notes.Add(new SongNote("X", midi, measure, offset, duration, 0, 0, "1", false, false, false, articulations, []));

        public void Grace(int measure, double offset, int midi, bool slash) =>
            notes.Add(new SongNote("X", midi, measure, offset, 0, 0, 0, "1", true, slash, false, [], []));

        public void Pedal(int measure, double offset, string type) =>
            pedals.Add(new SongPedal(measure, offset, 0, 1, type, "mark"));

        public void PedalSound(int measure, double offset, string value) =>
            pedals.Add(new SongPedal(measure, offset, 0, 1, "damper", "sound", value));

        public void Dynamic(int measure, double offset, string? mark, double? sound = null) =>
            dynamics.Add(new SongDynamic(measure, offset, 0, 0, mark, sound));

        public void Wedge(string kind, int startMeasure, double startOffset, int endMeasure, double endOffset) =>
            wedges.Add(new SongWedge(kind, 0, 0, startMeasure, startOffset, endMeasure, endOffset));

        public SongPerformance Build()
        {
            string json = JsonSerializer.Serialize(new SongPerformance(
                3, "musicxml", [new SongSource("score.musicxml", new string('0', 64))], false,
                [new SongPart(0, 2, "Piano")],
                [new SongPage(0, "score.musicxml", 0, measures, 0, 2.0 * measures, 2.0 * measures, "off")],
                Enumerable.Range(0, measures).Select(index => new SongMeasure(index, 0, (index + 1).ToString(),
                    2.0 * index, 2.0, 2.0, [2, 4], false, false, 0, null, false, null)).ToList(),
                playOrder ?? Enumerable.Range(0, measures).ToArray(),
                notes, pedals, dynamics, wedges, [], JsonDocument.Parse("{}").RootElement, []),
                new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower });
            return SongPerformance.Parse(json);
        }
    }
}
