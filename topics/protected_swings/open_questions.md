# Protected Swings Open Questions

- What exact algorithm defines the "series of down-close candles" or "series of up-close candles"?
- How should fair value gap based protected swings and sweep based protected swings be weighted if they disagree?
- Should a protected swing be stored only after bar close, or is there any justified intrabar mode?
- What is the minimum viable local swing model for version one:
  - pivot-based?
  - rolling-window based?
  - displacement-based?
