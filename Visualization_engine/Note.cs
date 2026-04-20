using Raylib_cs;
using System.Drawing;

namespace SynthesiaClone
{
    public class Note
    {
        public int TargetKeyIndex { get; set; }
        public int Velocity {get; set; }
        public double StartTime { get; set; } 
        public double Duration { get; set; }  
        public bool IsPlaying { get; set; } = false;
        public bool HasPlayed { get; set; } = false;

        public Raylib_cs.Color color {get; set;}

        public Note(int targetKeyIndex, double startTime, double duration, int velocity, Raylib_cs.Color color_)
        {
            TargetKeyIndex = targetKeyIndex;
            StartTime = startTime;
            Duration = duration;
            Velocity = velocity;
            color = color_;
        }
    }
}