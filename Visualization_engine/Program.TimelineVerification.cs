using System.Text.Json;
using Melanchall.DryWetMidi.Core;
using Melanchall.DryWetMidi.Interaction;

namespace SynthesiaClone;

/// <summary>
/// <c>--verify-timeline PERFORMANCE REFERENCE_MIDI OUTPUT_JSON</c>: compares the app's timeline for
/// an interpreted score with another program's MIDI export of the same score, for the expression
/// acceptance check. It touches no window, audio device or library.
/// </summary>
/// <remarks>
/// Bars are compared by placing each bar's beat on both tempo maps, so the bar check measures
/// the tempo alone. Notes are compared by matching each reference note to the app's nearest note
/// of the same pitch, which also checks the play order, and pedal by matching each change to the
/// nearest reference change in the same direction.
/// </remarks>
internal static partial class Program
{
	private const double NoteMatchSeconds = 0.25;

	private static int RunTimelineVerification(string[] arguments)
	{
		try
		{
			if (arguments.Length != 4)
			{
				throw new ArgumentException("Expected a performance, a reference MIDI file and an output path.");
			}
			SongPerformance performance = SongPerformance.Parse(File.ReadAllText(arguments[1]));
			MidiFile reference = MidiFile.Read(arguments[2]);
			if (reference.TimeDivision is not TicksPerQuarterNoteTimeDivision division)
			{
				throw new InvalidDataException("The reference MIDI file does not count ticks per quarter note.");
			}
			TempoMap tempoMap = reference.GetTempoMap();
			SongTimelineOptions options = SongTimelineOptions.For(new ExpressionOptions());
			(IReadOnlyList<(int Measure, double Beat, double Seconds)> bars, double endBeat, double endSeconds) =
				SongTimeline.BarTimes(performance, options);
			double origin = bars[0].Beat;
			double ReferenceSeconds(double beat) => TimeConverter.ConvertTo<MetricTimeSpan>(
				(long)Math.Round((beat - origin) * division.TicksPerQuarterNote), tempoMap).TotalSeconds;

			var barRows = bars.Select((bar, index) => new
			{
				index,
				measure = performance.Measures[bar.Measure].Number,
				app = Math.Round(bar.Seconds, 4),
				reference = Math.Round(ReferenceSeconds(bar.Beat), 4),
				difference = Math.Round(bar.Seconds - ReferenceSeconds(bar.Beat), 4)
			}).ToList();
			double referenceEnd = ReferenceSeconds(endBeat);

			SongPlayback playback = SongTimeline.Build(performance, options);
			List<(int Pitch, double Start, double End, int Velocity)> theirs = reference.GetNotes()
				.Select(note => ((int)note.NoteNumber,
					TimeConverter.ConvertTo<MetricTimeSpan>(note.Time, tempoMap).TotalSeconds,
					TimeConverter.ConvertTo<MetricTimeSpan>(note.EndTime, tempoMap).TotalSeconds,
					(int)note.Velocity))
				.ToList();
			Dictionary<int, List<Note>> oursByPitch = playback.Notes.GroupBy(static note => note.MidiPitch)
				.ToDictionary(static group => group.Key, static group => group.ToList());
			List<(double Onset, int Ours, int Theirs)> matched = [];
			List<double[]> unmatched = [];
			foreach ((int pitch, double start, _, int velocity) in theirs)
			{
				Note? nearest = oursByPitch.TryGetValue(pitch, out List<Note>? candidates)
					? candidates.MinBy(note => Math.Abs(note.StartTime - start))
					: null;
				if (nearest is null || Math.Abs(nearest.StartTime - start) > NoteMatchSeconds)
				{
					unmatched.Add([pitch, Math.Round(start, 4)]);
					continue;
				}
				matched.Add((nearest.StartTime - start, nearest.Velocity, velocity));
			}
			double[] onsetErrors = matched.Select(static pair => Math.Abs(pair.Onset)).Order().ToArray();

			List<PedalChange> referencePedal = SongCache.ReadMidiPedal(arguments[2]);
			double[] pedalErrors = playback.Pedal.Select(change =>
			{
				IEnumerable<PedalChange> same = referencePedal.Where(other => other.IsDown == change.IsDown);
				return same.Any() ? same.Min(other => Math.Abs(other.Time - change.Time)) : double.PositiveInfinity;
			}).Order().ToArray();

			var report = new
			{
				performance = Path.GetFullPath(arguments[1]),
				reference = Path.GetFullPath(arguments[2]),
				bars = barRows.Count,
				maxBarDifferenceSeconds = barRows.Max(row => Math.Abs(row.difference)),
				appEndSeconds = Math.Round(endSeconds, 4),
				referenceEndSeconds = Math.Round(referenceEnd, 4),
				lengthDifferencePercent = Math.Round(100.0 * (endSeconds - referenceEnd) / referenceEnd, 4),
				appLastNoteOff = Math.Round(playback.Notes.Max(static note => note.EndTime), 4),
				referenceLastNoteOff = Math.Round(theirs.Count == 0 ? 0 : theirs.Max(static note => note.End), 4),
				appNotes = playback.Notes.Count,
				referenceNotes = theirs.Count,
				matchedNotes = matched.Count,
				unmatchedReferenceNotes = unmatched.Count,
				firstUnmatchedReferenceNotes = unmatched.Take(20),
				onsetErrorMedianSeconds = onsetErrors.Length == 0 ? 0 : Math.Round(onsetErrors[onsetErrors.Length / 2], 4),
				onsetErrorP95Seconds = onsetErrors.Length == 0 ? 0 : Math.Round(onsetErrors[(int)(onsetErrors.Length * 0.95)], 4),
				velocityCorrelation = Math.Round(Correlation(matched.Select(static pair => (double)pair.Ours).ToArray(),
					matched.Select(static pair => (double)pair.Theirs).ToArray()), 4),
				velocityMeanAbsoluteDifference = matched.Count == 0 ? 0
					: Math.Round(matched.Average(static pair => Math.Abs(pair.Ours - pair.Theirs)), 2),
				appPedalChanges = playback.Pedal.Count,
				referencePedalChanges = referencePedal.Count,
				pedalErrorMedianSeconds = pedalErrors.Length == 0 ? 0 : Math.Round(pedalErrors[pedalErrors.Length / 2], 4),
				pedalErrorMaxSeconds = pedalErrors.Length == 0 ? 0 : Math.Round(pedalErrors[^1], 4),
				tempoMarks = performance.Tempos.Count,
				appPedal = playback.Pedal.Take(200).Select(static change => new[] { Math.Round(change.Time, 4), change.Value }),
				referencePedal = referencePedal.Take(200).Select(static change => new[] { Math.Round(change.Time, 4), change.Value }),
				barRows
			};
			File.WriteAllText(arguments[3], JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
			Console.WriteLine($"[TIMELINE] bars={report.bars} max_bar_difference={report.maxBarDifferenceSeconds:F4}s " +
				$"length_difference={report.lengthDifferencePercent:F3}% matched_notes={report.matchedNotes}/{report.referenceNotes}");
			return 0;
		}
		catch (Exception error)
		{
			Console.Error.WriteLine(error);
			return 1;
		}
	}

	private static double Correlation(double[] left, double[] right)
	{
		if (left.Length < 2)
		{
			return 0;
		}
		double meanLeft = left.Average();
		double meanRight = right.Average();
		double covariance = 0, varianceLeft = 0, varianceRight = 0;
		for (int index = 0; index < left.Length; index++)
		{
			covariance += (left[index] - meanLeft) * (right[index] - meanRight);
			varianceLeft += (left[index] - meanLeft) * (left[index] - meanLeft);
			varianceRight += (right[index] - meanRight) * (right[index] - meanRight);
		}
		return varianceLeft == 0 || varianceRight == 0 ? 0 : covariance / Math.Sqrt(varianceLeft * varianceRight);
	}
}
