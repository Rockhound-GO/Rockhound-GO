# Copilot Instructions for Rockhound GO

## Project Overview
**Rockhound GO** is a React-based web application for discovering and exploring rockhounding locations across the United States. It displays a searchable catalog of mining/fossil collection sites with detailed information about minerals, difficulty levels, access restrictions, and required tools.

## Architecture

### Tech Stack
- **Frontend**: React with Tailwind CSS for styling
- **Data**: Mock dataset (JSON-structured) with location objects containing coordinates, mineral types, and images
- **Icons**: Lucide React icon library
- **Styling**: Tailwind CSS via CDN with custom animations
- **Build**: Node.js environment (see `nova.js` for server setup)

### Core Components
1. **App Component** (`locations` file): Main container managing state for locations, search filtering, and expanded card views
2. **LocationCard**: Reusable card component displaying individual rockhounding sites with collapsible details
3. **Input**: Custom search input component mimicking shadcn/ui styling patterns

### Data Structure
Locations are objects with required properties:
```javascript
{
  id, name, lat, lng, type, description, minerals, 
  images, difficulty, access, tools
}
```
- `type`: Geological classification (Volcanic, Sedimentary, Metamorphic, Igneous)
- `difficulty`: Easy, Moderate, or Difficult
- `minerals`: Array of mineral names found at location
- **All images must include fallback handling** - use `onImageError` callback to replace with placeholder

## Key Patterns & Conventions

### Search/Filter Pattern
- Location filtering uses `.filter()` with multi-field search (name, minerals, type)
- Search is case-insensitive and filters ALL three fields simultaneously
- Implement in `filteredLocations` using `.toLowerCase().includes()`

### Image Management
- Use `PLACEHOLDER_IMAGE_URL()` function for broken image fallbacks
- Track image errors in state via `imageErrorCache` to prevent repeated failed requests
- Each image carousel controlled at card level with `currentImageIndex` state
- **Always implement `onImageError` callback** when rendering images

### Styling Conventions
- Color palette: Slate grays (slate-900 to slate-700 backgrounds), amber/orange for accents
- Card hover effects: Scale (1.05), border color change to amber
- Selected state uses `ring-2 ring-amber-500` with scale transform
- Icon colors align with semantic meaning (amber for gems, orange for location, sky for minerals)

### State Management
- Uses React hooks (`useState`, `useEffect`) for local component state
- No global state management—each component manages its own UI state
- Search term is app-level state, selection/image carousel is card-level state

## Development Workflow

### Running the Server
The `nova.js` file contains a simple HTTP server:
```bash
node nova.js  # or node server.mjs (commented as starting example)
# Listens on http://127.0.0.1:3000
```

### Security & Code Scanning
- **njsscan** GitHub Action runs on all PRs to main branch (see `.github/workflows/njsscan.yml`)
- Scans for Node.js security vulnerabilities and insecure code patterns
- Results uploaded to GitHub Security tab via SARIF format
- Ensure no security warnings before merging to main

### Branch Structure
- **main**: Production branch with security scanning
- **Rockhound-GO-patch-1**: Current development branch (active PR #1)

## Common Tasks

### Adding a New Location
1. Add object to `initialMockRockhoundingLocations` array in `locations` file
2. Ensure all required properties are present (id, name, minerals, images, etc.)
3. Test image URLs load correctly; configure fallback if needed

### Modifying Card Display
- Edit `LocationCard` component for visual changes
- Remember: `isSelected` state controls expanded view appearance
- Keep expandable content within the conditional `{isSelected && ...}` block

### Adding Search Filters
- Extend `filteredLocations` logic in App component
- New filters should work with `.filter()` method on locations array
- Update search placeholder text to reflect new capabilities

## File Organization
```
/
├── nova.js              # Server setup (simple HTTP server)
├── locations            # React App component with LocationCard
├── README.md            # GitHub profile README (template only)
└── .github/
    ├── copilot-instructions.md  # This file
    └── workflows/
        └── njsscan.yml  # Security scanning workflow
```

## Important Notes
- **No external backend**: All data is mock data defined in the locations file
- **Tailwind via CDN**: CSS and font loaded dynamically in component; don't rely on pre-compiled CSS
- **Icon library**: Uses Lucide React—verify icon names exist before implementing
- **Responsive design**: Grid layout changes at `md:` and `lg:` breakpoints for mobile/tablet/desktop
