using System.Runtime.CompilerServices;
using Raylib_cs;
using Color = Raylib_cs.Color;

namespace SynthesiaClone;

public sealed record Note(int TargetKeyIndex, double StartTime, double Duration, int Velocity, Color Color)
{
	public double EndTime => StartTime + Duration;

	public int MidiPitch => TargetKeyIndex + 21;

	public string PitchClass
	{
		get
		{
			int targetKeyIndex = TargetKeyIndex;
			if (targetKeyIndex < 0 || targetKeyIndex >= 88)
			{
				return string.Empty;
			}
			return PitchClassNames[MidiPitch % 12];
		}
	}

	private static readonly string[] PitchClassNames = new string[12]
	{
		"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A",
		"A#", "B"
	};

	[CompilerGenerated]
	private Note(Note original)
	{
		TargetKeyIndex = original.TargetKeyIndex;
		StartTime = original.StartTime;
		Duration = original.Duration;
		Velocity = original.Velocity;
		Color = original.Color;
	}
}
