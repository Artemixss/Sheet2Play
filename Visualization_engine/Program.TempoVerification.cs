using System.Diagnostics;
using System.Text.Json;

namespace SynthesiaClone;

/// <summary>
/// <c>--detect-tempo PDF STORE_DIRECTORY [PERFORMANCE]</c>: reads a PDF's printed tempo marks the way
/// READ PRINTED MARKS does, through the bridge's <c>tempo_marks.py</c> in the HOMR runtime, and
/// prints them as JSON. STORE_DIRECTORY stands in for the library, so the user's own store is not
/// touched. With a <c>performance.json</c> of a conversion of the PDF, it also prints the bar each
/// mark lands on in that song, as the TEMPO panel lists it.
/// </summary>
internal static partial class Program
{
	private static int RunTempoDetectionVerification(string[] arguments)
	{
		try
		{
			if (arguments.Length is not (3 or 4))
			{
				throw new ArgumentException("Expected a PDF, a store directory and optionally a performance.json.");
			}
			string pdf = Path.GetFullPath(arguments[1]);
			string store = Path.GetFullPath(arguments[2]);
			string source = SongCache.Sha256OfFile(pdf);
			Stopwatch clock = Stopwatch.StartNew();
			DetectedTempos detected = TempoDetection.Detect(store, OmrPipeline.DefaultBridgeDirectory, pdf, source,
				new Progress<(int Page, int Pages)>(static step => Console.Error.WriteLine($"[TEMPO] page {step.Page} of {step.Pages}")),
				background: false);
			SongPerformance? performance = arguments.Length == 4 ? SongPerformance.Parse(File.ReadAllText(arguments[3])) : null;
			IReadOnlyList<PrintedMark>? placed = performance is null ? null : TempoDetection.Place(detected, performance);
			Console.WriteLine(JsonSerializer.Serialize(new
			{
				reader_sha256 = detected.ReaderSha256,
				source_sha256 = detected.SourceSha256,
				seconds = Math.Round(clock.Elapsed.TotalSeconds, 2),
				pages = detected.Pages.Count,
				marks = detected.Marks.Select(static mark => new { mark.Page, mark.PageMeasure, mark.Bpm, mark.Unit, mark.Text }),
				placed = placed?.Select(mark => new
				{
					bar = mark.Measure is int measure ? SongTempoMaps.BarName(performance!, measure) : null,
					bpm = mark.Tempo?.Bpm,
					unit = mark.Tempo?.Unit.ToString(),
					words = mark.Words,
					usable = mark.Usable
				})
			}, new JsonSerializerOptions { WriteIndented = true }));
			return 0;
		}
		catch (Exception exception) when (exception is ArgumentException or IOException or UnauthorizedAccessException
			or JsonException or InvalidDataException or TempoDetectionException)
		{
			Console.Error.WriteLine("[TEMPO] " + exception.Message);
			return 1;
		}
	}
}
