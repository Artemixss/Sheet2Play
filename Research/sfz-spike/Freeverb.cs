namespace SfzSpike;

/// <summary>
/// Jezar's public-domain Freeverb (eight combs and four all-passes per channel), the same family
/// of reverb MeltySynth adds to the app's SoundFont piano, so the comparison is not dry against wet.
/// </summary>
public sealed class Freeverb
{
    private static readonly int[] CombTunings = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617];
    private static readonly int[] AllPassTunings = [556, 441, 341, 225];
    private const int StereoSpread = 23;
    private const float FixedGain = 0.015f;

    private readonly Comb[] combsLeft, combsRight;
    private readonly AllPass[] allPassesLeft, allPassesRight;

    public Freeverb(int sampleRate, float roomSize = 0.5f, float damping = 0.5f, float wet = 0.3f)
    {
        double scale = sampleRate / 44100.0;
        float feedback = roomSize * 0.28f + 0.7f;
        float damp = damping * 0.4f;
        combsLeft = CombTunings.Select(t => new Comb((int)(t * scale), feedback, damp)).ToArray();
        combsRight = CombTunings.Select(t => new Comb((int)((t + StereoSpread) * scale), feedback, damp)).ToArray();
        allPassesLeft = AllPassTunings.Select(t => new AllPass((int)(t * scale))).ToArray();
        allPassesRight = AllPassTunings.Select(t => new AllPass((int)((t + StereoSpread) * scale))).ToArray();
        Wet = wet;
    }

    public float Wet { get; }

    /// <summary>Adds the reverb to the signal in place.</summary>
    public void Process(float[] left, float[] right)
    {
        for (int index = 0; index < left.Length; index++)
        {
            float input = (left[index] + right[index]) * FixedGain;
            float outLeft = 0, outRight = 0;
            for (int comb = 0; comb < combsLeft.Length; comb++)
            {
                outLeft += combsLeft[comb].Process(input);
                outRight += combsRight[comb].Process(input);
            }
            for (int pass = 0; pass < allPassesLeft.Length; pass++)
            {
                outLeft = allPassesLeft[pass].Process(outLeft);
                outRight = allPassesRight[pass].Process(outRight);
            }
            left[index] += outLeft * Wet;
            right[index] += outRight * Wet;
        }
    }

    private sealed class Comb(int size, float feedback, float damp)
    {
        private readonly float[] buffer = new float[size];
        private int position;
        private float store;

        public float Process(float input)
        {
            float output = buffer[position];
            store = output * (1 - damp) + store * damp;
            buffer[position] = input + store * feedback;
            position = position + 1 == buffer.Length ? 0 : position + 1;
            return output;
        }
    }

    private sealed class AllPass(int size)
    {
        private readonly float[] buffer = new float[size];
        private int position;

        public float Process(float input)
        {
            float buffered = buffer[position];
            buffer[position] = input + buffered * 0.5f;
            position = position + 1 == buffer.Length ? 0 : position + 1;
            return buffered - input;
        }
    }
}
