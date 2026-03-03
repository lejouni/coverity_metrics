# Converting the Presentation to PowerPoint

This guide shows you how to convert `Coverity_Metrics_Presentation.md` into a PowerPoint presentation, or generate one directly with the included Python script.

## Option 1: Python Script (Recommended)

The repository includes `create_presentation.py`, which generates `Coverity_Metrics_Presentation.pptx` directly using `python-pptx` — no external tools required.

### Install dependency
```bash
pip install python-pptx
```

### Generate the PPTX
```bash
python create_presentation.py
```

This writes `Coverity_Metrics_Presentation.pptx` to the project root.

## Option 2: Using Pandoc

### Install Pandoc
Download from: https://pandoc.org/installing.html

### Convert to PowerPoint
```bash
pandoc Coverity_Metrics_Presentation.md -o Coverity_Metrics_Presentation.pptx
```

### With Custom Theme
```bash
pandoc Coverity_Metrics_Presentation.md -o Coverity_Metrics_Presentation.pptx --reference-doc=template.pptx
```

## Option 3: Using Marp

### Install Marp CLI
```bash
npm install -g @marp-team/marp-cli
```

### Convert to PowerPoint
```bash
marp Coverity_Metrics_Presentation.md --pptx -o Coverity_Metrics_Presentation.pptx
```

## Option 4: Manual Import

1. Open PowerPoint
2. Go to **File > Open**
3. Select the `.md` file
4. PowerPoint will convert it automatically (may vary by version)

## Option 5: Copy and Paste

1. Open the Markdown file in a text editor
2. Each `---` separator marks a new slide
3. Copy content for each slide
4. Paste into PowerPoint slides manually

## Slide Structure

The presentation has **37 slides** covering:

1. Title & Introduction (2 slides)
2. What is Coverity Metrics + The Challenge (2 slides)
3. Key Features + Dashboard Tabs (2 slides)
4. Security Compliance — OWASP Top 10 + CWE Top 25 (2 slides)
5. Technical Debt & Leaderboards (2 slides)
6. Trend Analysis (1 slide)
7. Installation & Setup (3 slides)
8. CLI Commands & Workflows (3 slides)
9. Use Cases (4 slides)
10. Advanced Features (1 slide)
11. What's New (1 slide)
12. Architecture & Performance (2 slides)
13. Metrics Categories (3 slides)
14. Database Schema & Security (2 slides)
15. Extensibility & FAQ (2 slides)
16. Roadmap & Getting Started (2 slides)
17. Resources & Success Stories (2 slides)
18. Summary & Conclusion (3 slides)

## Customization Tips

### Add Your Branding
- Replace `[Your Email]` and `[Repository URL]` in the last slide
- Add company logo to title slide
- Adjust color scheme to match corporate branding

### Add Screenshots
Consider adding screenshots for:
- Dashboard overview (slide 4)
- OWASP Top 10 view (slide 6)
- CWE Top 25 view (slide 7)
- Technical Debt display (slide 8)
- Leaderboards (slide 9)
- Trend charts (slide 10)

### Update "What's New" Slide
The "What's New" slide currently references v1.0.6. Update it to v1.0.9 and summarise
the three fixes in this release before presenting.

### Adjust Content
- Remove slides not relevant to your audience
- Add company-specific success stories
- Include actual metrics from your environment
- Add speaker notes for each slide

## Best Practices

1. **Keep it Visual**: Add charts and screenshots where possible
2. **Use Animations**: Reveal bullet points progressively
3. **Add Transitions**: Use subtle slide transitions
4. **Include Examples**: Show real dashboard outputs
5. **Practice Timing**: Aim for 1-2 minutes per slide (37-74 min total)

## For Different Audiences

### Executive Presentation (15 minutes)
Keep slides: 1-5, 6-7, 17-20, 35-37

### Technical Deep-Dive (60 minutes)
Use all slides, add technical demos

### Quick Demo (10 minutes)
Keep slides: 1-2, 4-5, 11-13, 16, 37

## Notes

- The Markdown uses `#` for titles and `###` for content
- Code blocks are formatted with triple backticks
- Tables are used for feature comparisons
- Emojis are included for visual appeal (may need font support)
