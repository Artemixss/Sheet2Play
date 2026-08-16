using System;
using System.Collections.Generic;
using System.Linq;
using Raylib_cs;
using Color = Raylib_cs.Color;

namespace SynthesiaClone;

public class Keyboard
{
	private readonly List<PianoKey> drawOrder = new List<PianoKey>();

	private int _screenWidth;

	private int _hitLineY;

	private int _keyboardHeight;

	public PianoKey[] Keys { get; }

	public Keyboard(int screenWidth, int hitLineY, int keyboardHeight = 150)
	{
		Keys = new PianoKey[88];
		Resize(screenWidth, hitLineY, keyboardHeight);
	}

	public void Resize(int screenWidth, int hitLineY, int keyboardHeight)
	{
		if (screenWidth <= 0)
		{
			throw new ArgumentOutOfRangeException("screenWidth");
		}
		if (keyboardHeight <= 0)
		{
			throw new ArgumentOutOfRangeException("keyboardHeight");
		}
		_screenWidth = screenWidth;
		_hitLineY = hitLineY;
		_keyboardHeight = keyboardHeight;
		drawOrder.Clear();
		string[] array = new string[12]
		{
			"C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A",
			"Bb", "B"
		};
		int[] source = new int[5] { 1, 3, 6, 8, 10 };
		int num = 0;
		for (int i = 0; i < 88; i++)
		{
			int num2 = i + 21;
			int value = num2 % 12;
			if (!source.Contains(value))
			{
				int num3 = (int)((float)(num * _screenWidth) / 52f);
				int num4 = (int)((float)((num + 1) * _screenWidth) / 52f);
				PianoKey pianoKey = Keys[i] ?? new PianoKey();
				pianoKey.Index = i;
				pianoKey.IsBlack = false;
				pianoKey.X = num3;
				pianoKey.Y = _hitLineY;
				pianoKey.Width = num4 - num3;
				pianoKey.Height = _keyboardHeight;
				pianoKey.Label = array[num2 % 12];
				Keys[i] = pianoKey;
				drawOrder.Add(pianoKey);
				num++;
			}
		}
		num = 0;
		int num5 = (int)((float)_screenWidth / 52f * 0.6f);
		for (int j = 0; j < 88; j++)
		{
			int num6 = j + 21;
			int value2 = num6 % 12;
			if (source.Contains(value2))
			{
				PianoKey pianoKey2 = drawOrder[num - 1];
				int num7 = pianoKey2.X + pianoKey2.Width;
				PianoKey pianoKey3 = Keys[j] ?? new PianoKey();
				pianoKey3.Index = j;
				pianoKey3.IsBlack = true;
				pianoKey3.X = num7 - num5 / 2;
				pianoKey3.Y = _hitLineY;
				pianoKey3.Width = num5;
				pianoKey3.Height = Math.Max(1, (int)Math.Round((double)_keyboardHeight * 0.6));
				Keys[j] = pianoKey3;
				drawOrder.Add(pianoKey3);
				pianoKey3.Label = array[num6 % 12];
			}
			else
			{
				num++;
			}
		}
	}

	public void Draw()
	{
		Color color = new Color(230, 230, 230, 255);
		Color color2 = new Color(210, 210, 210, 255);
		foreach (PianoKey item in drawOrder)
		{
			if (!item.IsBlack)
			{
				if (item.IsPressed)
				{
					Raylib.DrawRectangle(item.X, item.Y, item.Width, item.Height, Color.DarkBlue);
					Raylib.DrawText(item.Label, item.X + 5, item.Y + item.Height - 20, 10, Color.Black);
					Raylib.DrawRectangleLines(item.X, item.Y, item.Width, item.Height, Color.LightGray);
				}
				else
				{
					Raylib.DrawRectangle(item.X, item.Y, item.Width, item.Height, color);
					Raylib.DrawText(item.Label, item.X + 5, item.Y + item.Height - 20, 10, Color.Black);
					Raylib.DrawRectangleLines(item.X, item.Y, item.Width, item.Height, Color.LightGray);
				}
			}
			else if (item.IsPressed)
			{
				Raylib.DrawRectangle(item.X, item.Y, item.Width, item.Height, Color.Gray);
				Raylib.DrawText(item.Label, item.X + 2, item.Y + item.Height - 15, 10, color2);
			}
			else
			{
				Raylib.DrawRectangle(item.X, item.Y, item.Width, item.Height, Color.Black);
				Raylib.DrawText(item.Label, item.X + 2, item.Y + item.Height - 15, 10, color2);
			}
		}
	}
}
