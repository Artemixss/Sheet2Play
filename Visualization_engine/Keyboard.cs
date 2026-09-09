using System;
using System.Collections.Generic;
using System.Linq;
using Raylib_cs;
using Color = Raylib_cs.Color;

namespace SynthesiaClone;

public class Keyboard
{
	private const int KeyCount = 88;
	private const int WhiteKeyCount = 52;
	private const int LowestMidiPitch = 21;

	private static readonly string[] NoteNames =
	[
		"C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"
	];

	private static readonly int[] BlackPitchClasses = [1, 3, 6, 8, 10];

	private static readonly Color WhiteKeyFill = new Color(230, 230, 230, 255);
	private static readonly Color BlackKeyLabel = new Color(210, 210, 210, 255);

	// White keys first, then black, so the black keys paint on top of their neighbours.
	private readonly List<PianoKey> drawOrder = new List<PianoKey>();

	private int screenWidth;

	private int hitLineY;

	private int keyboardHeight;

	public PianoKey[] Keys { get; }

	public Keyboard(int screenWidth, int hitLineY, int keyboardHeight = 150)
	{
		Keys = new PianoKey[KeyCount];
		Resize(screenWidth, hitLineY, keyboardHeight);
	}

	public void Resize(int screenWidth, int hitLineY, int keyboardHeight)
	{
		if (screenWidth <= 0)
		{
			throw new ArgumentOutOfRangeException(nameof(screenWidth));
		}
		if (keyboardHeight <= 0)
		{
			throw new ArgumentOutOfRangeException(nameof(keyboardHeight));
		}
		this.screenWidth = screenWidth;
		this.hitLineY = hitLineY;
		this.keyboardHeight = keyboardHeight;
		drawOrder.Clear();

		int whiteKeyIndex = 0;
		for (int index = 0; index < KeyCount; index++)
		{
			int pitchClass = (index + LowestMidiPitch) % 12;
			if (BlackPitchClasses.Contains(pitchClass))
			{
				continue;
			}

			// Edges are derived from the key's ordinal rather than accumulated, so rounding
			// cannot drift across the keyboard and leave a gap at the top end.
			int left = (int)((float)(whiteKeyIndex * this.screenWidth) / WhiteKeyCount);
			int right = (int)((float)((whiteKeyIndex + 1) * this.screenWidth) / WhiteKeyCount);
			PianoKey key = Keys[index] ?? new PianoKey();
			key.Index = index;
			key.IsBlack = false;
			key.X = left;
			key.Y = this.hitLineY;
			key.Width = right - left;
			key.Height = this.keyboardHeight;
			key.Label = NoteNames[pitchClass];
			Keys[index] = key;
			drawOrder.Add(key);
			whiteKeyIndex++;
		}

		int blackKeyWidth = (int)((float)this.screenWidth / WhiteKeyCount * 0.6f);
		int whiteKeysSeen = 0;
		for (int index = 0; index < KeyCount; index++)
		{
			int pitchClass = (index + LowestMidiPitch) % 12;
			if (!BlackPitchClasses.Contains(pitchClass))
			{
				whiteKeysSeen++;
				continue;
			}

			// Straddles the boundary between the white key to its left and the next one.
			PianoKey leftNeighbour = drawOrder[whiteKeysSeen - 1];
			int boundary = leftNeighbour.X + leftNeighbour.Width;
			PianoKey key = Keys[index] ?? new PianoKey();
			key.Index = index;
			key.IsBlack = true;
			key.X = boundary - (blackKeyWidth / 2);
			key.Y = this.hitLineY;
			key.Width = blackKeyWidth;
			key.Height = Math.Max(1, (int)Math.Round((double)this.keyboardHeight * 0.6));
			key.Label = NoteNames[pitchClass];
			Keys[index] = key;
			drawOrder.Add(key);
		}
	}

	public void Draw()
	{
		foreach (PianoKey key in drawOrder)
		{
			if (!key.IsBlack)
			{
				Raylib.DrawRectangle(key.X, key.Y, key.Width, key.Height,
					key.IsPressed ? Color.DarkBlue : WhiteKeyFill);
				Raylib.DrawText(key.Label, key.X + 5, key.Y + key.Height - 20, 10, Color.Black);
				Raylib.DrawRectangleLines(key.X, key.Y, key.Width, key.Height, Color.LightGray);
			}
			else
			{
				Raylib.DrawRectangle(key.X, key.Y, key.Width, key.Height,
					key.IsPressed ? Color.Gray : Color.Black);
				Raylib.DrawText(key.Label, key.X + 2, key.Y + key.Height - 15, 10, BlackKeyLabel);
			}
		}
	}
}
