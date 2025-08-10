# cogs/galaxy_generator.py - Fixed to align with gate lore
import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import re
import io
import asyncio
import psycopg2
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from utils.history_generator import HistoryGenerator
import collections

class GalaxyGeneratorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.auto_shift_task = None
        self.gate_check_task = None
        # Lore-appropriate name lists
        self.location_prefixes = [
            "A-1", "AO", "Acheron", "Aegis", "Alpha", "Amber", "Anchor", "Annex",
            "Apex", "Apollo", "Arc", "Archive", "Ares", "Aries", "Armstrong", "Ash",
            "Ashfall", "Atlas", "Azure", "B-2", "Barren", "Base", "Bastion", "Bay",
            "Bent", "Beta", "Black", "Blackwood", "Bleak", "Block", "Blue", "Bluewater",
            "Breaker", "Broad", "Broadway", "Bronze", "Bulwark", "C-3", "CN", "CT",
            "Cadmus", "Camp", "Cancer", "Canyon", "Central", "Cerberus", "Charon", "Chi",
            "Chronos", "Citadel", "Clear", "Clearwater", "Cobalt", "Cold", "Coldiron", "Conduit",
            "Copernicus", "Copper", "Crater", "Crest", "Crimson", "Crimsonpeak", "Crux", "Curie",
            "D-4", "DS", "DV", "Daedalus", "Dark", "Darwich", "Darwin's", "Deep",
            "Deepwater", "Delta", "Depot", "Distant", "Distantshore", "Drift", "Dry", "Dryland",
            "Dull", "Dust", "Dustveil", "E-5", "EX", "Eastern", "Echo", "Edge",
            "Edison", "Eighteen", "Eighth", "Eighty", "Elephant's", "Eleven", "Elysium", "Emerald",
            "Endeavor", "Epsilon", "Erebus", "Eta", "F-6", "Faint", "Fallout", "Field",
            "Fifth", "Fifty", "First", "Five", "Flat", "Fort", "Forty", "Forty-Six",
            "Four", "Fourteen", "Fourth", "Fringe", "Frontier", "G-7", "GR", "Gaea",
            "Galilei", "Gamma", "Garrison", "Gate", "Gemini", "Glacier", "Gloom", "Glory",
            "Gloryforge", "Golden", "Goldenrod", "Gray", "Greater", "Grid", "H-8", "Hades",
            "Hard", "Haven", "Hawking", "Heavy", "Hephaestus", "High", "Highpoint", "Hold",
            "Hollow", "Hollowstone", "Honor", "Honorbound", "Hub", "Humanity's", "Hundred", "Hydra",
            "I-9", "Indigo", "Iota", "Iron", "Ironclad", "Ironwood", "Isolated", "J-10",
            "Justice", "K-11", "KX", "Kappa", "Kepler", "L-6", "LN", "Lambda",
            "Lavender", "Legacy", "Leo", "Liberty", "Liberty Bell", "Libra", "Lifeless", "Line",
            "Lonely", "Long", "Longview", "Low", "Lowdown", "Lower", "Lyra", "M-13",
            "MA", "MR", "Mariner", "Maroon", "Mesa", "Mighty", "Module", "Mound",
            "Mournful", "Mu", "Murk", "Muted", "N-14", "Narrow", "Neo", "New",
            "Newton", "Nexus", "Nine", "Nineteen", "Ninety", "Ninety-Two", "Node", "Northern",
            "Nova", "Nu", "Nyx", "OB", "Oasis", "Obscure", "Obsidian", "Ochre",
            "Old", "Olympus", "Omega", "Omicron", "One", "Orion", "Outpost", "Overgrown",
            "P-16", "PS", "Pale", "Paleview", "Paragon", "Persephone", "Petrified", "Phi",
            "Pi", "Pierced", "Pisces", "Plateau", "Platform", "Platinum", "Plum", "Point",
            "Port", "Post", "Prometheus", "Providence", "Psi", "Pulse", "Q-17", "Quiet",
            "Quietude", "R-12", "RQ", "RX", "Radiant", "Radiantfield", "Range", "Ravaged",
            "Red", "Redstone", "Reef", "Relay", "Remote", "Resolve", "Rhea", "Rho",
            "Ridge", "Ring", "Rough", "Ruined", "Rust", "S-19", "ST", "SV",
            "Sanctuary", "Sands", "Scarlet", "Scorpio", "Scrap", "Secluded", "Second", "Sector",
            "Sentinel", "Settlement", "Seven", "Seventeen", "Seventy", "Seventy-Nine", "Shade", "Shadow",
            "Shadowbrook", "Shadowed", "Shaft", "Shallows", "Sharp", "Shattered", "Shelter", "Short",
            "Shortwave", "Sigma", "Silent", "Silentbrook", "Silver", "Silverleaf", "Site", "Sixteen",
            "Sixth", "Sixty", "Slag", "Soft", "Sol", "Solemn", "Somber", "Soot",
            "Southern", "Span", "Spire", "Stark", "Station", "Steel", "Steelheart", "Still",
            "Stonefall", "Stonewalled", "Strip", "Styx", "T-20", "TR", "TX", "Talon",
            "Tau", "Teal", "Tenth", "Terra", "Theta", "Thin", "Third", "Thirteen",
            "Thirty", "Thirty-Two", "Thorn", "Thousand", "Three", "Tired", "Titan", "Tomb",
            "Torrent", "Tower", "Triumph", "Tsiolkovsky", "Tundra", "Twelve", "Twenty", "Twenty-One",
            "Twin", "Twinfalls", "Two", "UT", "Unity", "Unitygate", "Upsilon", "V-8",
            "Vanguard", "Veil", "Venan's", "Verdant", "Veridian", "Vesper", "Vetaso's", "Violet",
            "Virgo", "Vision", "Void", "Vortex", "W-23", "Waste", "Western", "White",
            "Whitewash", "Wild", "Worn", "Wreck", "X-9", "Xi", "Y-25", "Z-21",
            "Z-26", "ZC", "Zero", "Zeta", "Zinc"
        ]
        
        self.location_names = [
            "Abyss", "Access", "Acropolis", "Aether", "Alcove", "Alliance", "Alpha", "Altitude",
            "Anchor", "Apex", "Apollo", "Aqueduct", "Arc", "Arch", "Archive", "Arcology",
            "Area", "Ariel", "Armature", "Array", "Arrokoth", "Artemis", "Artery", "Ascent",
            "Ashen", "Asteroid", "Atlas", "Aurora", "Awareness", "Axle", "Balance", "Barren",
            "Base", "Basilica", "Basin", "Bastille", "Bastion", "Battleship", "Bay", "Beacon",
            "Beam", "Being", "Bellow", "Belt", "Bend", "Bennu", "Beta", "Blight",
            "Blink", "Block", "Bluff", "Bomber", "Border", "Borealis", "Brace", "Breadth",
            "Bridge", "Brimstone", "Bristle", "Brood", "Buffer", "Building", "Bulwark", "Burn",
            "Cairn", "Callisto", "Canyon", "Cargo", "Carrier", "Cascade", "Casing",
            "Cassini", "Cauldron", "Causeway", "Cavity", "Cellar", "Centauri", "Centra", "Central",
            "Ceres", "Chandra", "Chang'e", "Channel", "Chaos", "Charon", "Chasm", "Chicxulub",
            "Circle", "Citadel", "City", "Clamp", "Clay", "Cloak", "Coalition", "Coil",
            "Coldiron", "Coliseum", "Column", "Comet", "Commonwealth", "Compass", "Concept",
            "Conclave", "Concord", "Concordat", "Conduit", "Consortium", "Construct", "Containment",
            "Core", "Corona", "Corvette", "Cosmos", "Cove", "Covenant", "Craft", "Crag",
            "Crane", "Cranny", "Crater", "Creation", "Creep", "Crest", "Cross", "Crown",
            "Crucible", "Cruiser", "Crypt", "Curiosity", "Current", "Curve", "Cut", "Dagger",
            "Damper", "Dark", "Dawn", "Decay", "Deep", "Deimos", "Delta", "Deluge",
            "Depot", "Depression", "Depth", "Descent", "Destroyer", "Dip", "Disk", "District",
            "Ditch", "Divide", "Dock", "Domain", "Dome", "Dominion", "Door", "Dreadnought",
            "Dredge", "Drift", "Drop", "Dropship", "Dross", "Duct", "Dusk", "Echo",
            "Eclipse", "Ecumenopolis", "Edge", "Edifice", "Elevation", "Ember", "Emergence", "Empire",
            "Enceladus", "Enclave", "Enclosure", "Endeavor", "Ender", "Engine", "Entrance", "Entry",
            "Epsilon", "Eris", "Escort", "Essence", "Establishment", "Establisment", "Eternity", "Europa",
            "Existence", "Exit", "Expanse", "Fall", "Federation", "Fell", "Fermi", "Field",
            "Fighter", "First", "Fissure", "Fjord", "Flak", "Flat", "Flicker", "Flood",
            "Flow", "Flume", "Fold", "Foothold", "Forage", "Foremost", "Forge", "Form",
            "Fortress", "Forum", "Foundation", "Foundry", "Fount", "Fragment", "Frame", "Framework",
            "Freedom", "Freighter", "Frigate", "Frontier", "Galaxy", "Galileo", "Gamma", "Ganymede",
            "Gap", "Garrison", "Gash", "Genesis", "Ghost", "Girder",
            "Glare", "Glint", "Glitch", "Globe", "Gorge", "Graft", "Grid",
            "Grind", "Ground", "Gunship", "Gutter", "Habitat", "Hallow", "Hangar", "Harmony",
            "Haumea", "Haven", "Heart", "Height", "Helios", "Helix", "Hermes",
            "Herschel", "Highpoint", "Hinge", "Hollow", "Hope", "Horizon", "Hub", "Hubble",
            "Hull", "Husk", "Huskline", "Hygiea", "Icefall", "Idea", "Infinity", "Inlet",
            "Interceptor", "Io", "Ironline", "Itokawa", "Ixion", "Junction", "Juno", "Jupiter",
            "Keep", "Kepler", "Keystone", "Knot", "Knuckle", "Lander", "Lantern", "Lastlight",
            "Latch", "Lattice", "Lead", "Ledge", "Legacy", "Length", "Liberty", "Life",
            "Lift", "Line", "Locus", "Loom", "Loop", "Lot",
            "Luna", "Lurk", "Magma", "Magnus", "Makemake", "Mandate", "Manicouagan", "Mantle",
            "Mariner", "Mars", "Matrix", "Maul", "Megacity", "Meridian", "Mesa", "Mesh",
            "Metro", "Metropolis", "Midday", "Midnight", "Mill", "Mind", "Miranda", "Mire",
            "Module", "Mold", "Moldspore", "Moon", "Mouth", "Murk", "Nadir", "Narrow", "Nebula",
            "Neptune", "Nest", "Net", "Network", "New Horizons", "Nexus", "Niche", "Night",
            "Nimbus", "Node", "Nook", "Noon", "Nova", "Nox", "Oberon", "Olympus",
            "Opportunity", "Orb", "Orbit", "Orbiter", "Orcus", "Order", "Origin", "Outlet",
            "Outpost", "Outreach", "Outset", "Overlook", "Overpass", "Pale", "Palisade", "Pallas",
            "Panorama", "Pantheon", "Pass", "Passage", "Path", "Pathfinder", "Patrol", "Pattern",
            "Peak", "Perseverance", "Phobos", "Phoenix", "Pillar", "Pinnacle", "Pioneer", "Pipe",
            "Pit", "Pith", "Place", "Plain", "Planck", "Planet", "Plant", "Platform",
            "Plinth", "Plot", "Plume", "Pocket", "Point", "Polaris", "Popigai",
            "Portal", "Preserve", "Prima", "Prime", "Principle", "Promise", "Prospect", "Protectorate",
            "Providence", "Proxima", "Pulse", "Pusher", "Quadrant", "Quaoar", "Quarter", "Quench",
            "Quill", "Rack", "Radiance", "Rampart", "Range", "Rasp", "Ravine",
            "Reach", "Reality", "Realm", "Recess", "Reclaim", "Redoubt", "Refuge", "Region",
            "Relay", "Reliance", "Remnant", "Republic", "Rescour", "Reserve", "Resolve", "Resonance",
            "Resource", "Retreat", "Rhythm", "Ridge", "Rift", "Ring", "Rise", "Roost",
            "Root", "Rosetta", "Rot", "Run", "Rush", "Ryugu", "Salacia", "Sanctuary",
            "Sanctum", "Saturn", "Scald", "Scar", "Scour", "Scout", "Scrim", "Scrub",
            "Search", "Searchlight", "Sector", "Sedna", "Seep", "Segment", "Serenity", "Settlement",
            "Shackle", "Shaft", "Shard", "Shatter", "Shear", "Shelf", "Shell", "Shelter",
            "Ship", "Shiver", "Shoal", "Shroud", "Shunt", "Shuttle", "Sigma", "Signal",
            "Silt", "Singularity", "Sink", "Sirius", "Site", "Skyline", "Slag", "Slope",
            "Sluice", "Smelt", "Socket", "Sojourner", "Solace", "Solstice", "Solum", "Soul",
            "Sound", "Source", "Span", "Sphere", "Spindle", "Spiral", "Spire", "Spirit",
            "Spitzer", "Splendor", "Spoil", "Spot", "Sprawl", "Spring", "Spur", "Stack",
            "Stain", "Stake", "Stardust", "Static", "Stead", "Stem", "Steppe",
            "Steward", "Stitch", "Strait", "Strand", "Stray", "Stream", "Stretch", "Strip",
            "Structure", "Strut", "Subway", "Sudbury", "Summit", "Sump", "Sunrise", "Sunset",
            "Support", "Surge", "Swift", "Syndicate", "Tangle", "Tanker", "Terminal", "Terminus",
            "Terra", "Terrace", "Territory", "Tess", "Tether", "Theta", "Thought", "Thresh",
            "Threshold", "Thrush", "Tide", "Tint", "Titan", "Titania", "Tithe", "Torrent",
            "Tower", "Trace", "Transport", "Triton", "Triumph", "Trough", "Truss", "Truth",
            "Tube", "Tug", "Tunnel", "Tusk", "Twilight", "Twist", "Ultima", "Ultima Thule",
            "Umbriel", "Underpass", "Union", "Unity", "Universe", "Uranus", "Valley", "Vanguard",
            "Varuna", "Vault", "Vega", "Vetasol", "Venan", "Venera", "Venus", "Verge",
            "Vesper", "Vessel", "Vesta", "Viaduct", "Vibration", "Victory", "View", "Viking",
            "Vise", "Vista", "Void", "Voyager", "Vredefort", "Wake", "Ward", "Waste",
            "Watch", "Wave", "Web", "Webb", "Wellspring", "Whisk", "Wick", "Width",
            "Wither", "Works", "World", "Wrack", "Yard", "Zenith", "Zephyr", "Zeta",
            "Zond", "Zone"
        ]
        
        self.system_names = [
            "18 Delphini", "47 Ursae Majoris", "55 Cancri", "83 Leonis", "92-Alpha", "A-14", "Achernar", "Acheron",
            "Achilles", "Acrux", "Adhafera", "Aethel", "Aetheria", "Alcor", "Alcyone", "Aldebaran",
            "Algieba", "Algol", "Alhena", "Alioth", "Aljanah", "Alkaid", "Almach", "Alnair",
            "Alnilam", "Alpha Centauri", "Alphard", "Alpheratz", "Alphirk", "Alrakis", "Alrescha", "Altair",
            "Altinak", "Aludra", "Ancha", "Andromeda", "Ankaa", "Anomaly", "Antares", "Antennae",
            "Apex", "Aphrodite", "Apollo", "Arcturus", "Ares", "Arrokoth", "Artemis", "Ascella",
            "Asphodel", "Asteria", "Astral", "Athena", "Atlas", "Atria", "Avior", "Axiom",
            "Azelfafage", "Azha", "Barnard", "Baten", "Becrux", "Bennu", "Betelgeuse", "Biham",
            "Black Hole", "Blackeye", "Boomerang", "Bubble", "Bunda", "California", "Canopus", "Capella",
            "Caph", "Carina", "Cartwheel", "Casper", "Castor", "Celaeno", "Celeste", "Celestia",
            "Celestial", "Cenotaph", "Centaurus A", "Ceres", "Chaos", "Charon", "Chicxulub", "Chrono",
            "Cocytus", "Coeus", "Cone", "Constellation", "Core Worlds", "Corona", "Corvus", "Cosmic",
            "Cosmic Dust", "Cosmica", "Cosmo", "Cosmos", "Crab", "Crius", "Cronus", "Cursa",
            "Cygnus Loop", "Cygnus X-1", "Daedalus", "Dark Matter", "Deep Space", "Demeter", "Deneb", "Denebola",
            "Dimensional", "Dionysus", "Diphda", "Dreadnought", "Dubhe", "Dumbbell", "Eagle", "Earth",
            "Echo", "Ecliptic", "Electra", "Elephant's Trunk", "Elnath", "Eltanin", "Elysium", "Enif",
            "Epimetheus", "Epsilon Eridani", "Erebus", "Eris", "Event Horizon", "Expanse", "Eye of God", "Felta",
            "Flame", "Fomalhaut", "Foundry", "Fox Fur", "Fringe", "Frontier Space", "Furud", "GJ 667 C",
            "Gaia", "Galactic", "Gamma Cephei", "Genesis", "Gienah", "Gl 581", "Gliese", "Gonggong",
            "Groombridge 34", "HD 10647", "HD 219134", "HD 40307", "HR 8832", "Hadar", "Hades", "Haumea",
            "Heart", "Helix", "Hephaestus", "Hera", "Hercules", "Hermes", "Hestia", "Heze",
            "Homam", "Horsehead", "Hydor", "Hyperion", "Hyperspace", "Hypnos", "Iapetus", "Icarus",
            "Illuzhe", "Inner Rim", "Intergalactic", "Interstellar", "Iota Horologii", "Itokawa", "Ixion", "Izar",
            "Jabbah", "Jason", "Jellyfish", "Juno", "Jupiter", "Kaelen", "Kaffaljidhma", "Kapteyn",
            "Kaus", "Kepler-186", "Kitalpha", "Kochab", "Kore", "Kornephoros", "Kraz", "Kronos",
            "LHS 1140", "Lacaille", "Lacaille 9352", "Lagoon", "Lalande 21185", "Langvar", "Larawag", "Lethe",
            "Local Arm", "Lost Sector", "Luminary", "Lunar", "Luyten", "MacGregor", "Magnetar", "Maia",
            "Makemake", "Manicouagan", "Marfik", "Markab", "Mars", "Menkalinan", "Menkar", "Merak",
            "Mercury", "Merope", "Messier 87", "Miaplacidus", "Mid Rim", "Mimosa", "Minkowski's Butterfly", "Mintaka",
            "Mira", "Mirfak", "Mnemosyne", "Moros", "Mu Arae", "Muliphein", "NGC 2440", "NGC 6302",
            "Nadir", "Nash", "Nashira", "Navi", "Nebula Prime", "Nebular", "Neptune", "Neutron Star",
            "Nihal", "Norma Arm", "Nu Lupi", "Nunki", "Nyx", "Nyxos", "Oblivion", "Oceanus",
            "Odysseus", "Okul", "Olympus", "Orcus", "Orion", "Orion Arm", "Oryx", "Ouranos",
            "Outer Arm", "Outer Rim", "Outland", "PSR B1257+12", "Pallas", "Paradox", "Peacock", "Pelican",
            "Periphery", "Persephone", "Perseus", "Perseus Arm", "Phlegethon", "Phoebe", "Pillars of Creation", "Pinwheel",
            "Pleione", "Pluto", "Polaris", "Pollux", "Pontus", "Popigai", "Porrima", "Poseidon",
            "Procyon", "Procyon B", "Prometheus", "Proxima Centauri", "Pulsar", "Purin", "Quantum", "Quaoar",
            "Quasar", "Rasalgethi", "Rasalhague", "Rastaban", "Red Giant", "Red Rectangle", "Regalis", "Regulus",
            "Reliquary", "Requiem", "Rhea", "Rigel", "Rigil Kentaurus", "Rim", "Ring", "Rosette",
            "Ross", "Ross 128", "Rotanev", "Ruchbah", "Ryugu", "Sabik", "Sadalbari", "Sadalmelik",
            "Sadalsuud", "Sagittarius Arm", "Saiph", "Salacia", "Sanctuary", "Sargas", "Saturn", "Schedar",
            "Scutum-Centaurus Arm", "Sedna", "Sepulchre", "Serenity", "Sharpless 2-106", "Shaula", "Sigma Draconis", "Silence",
            "Simeis 147", "Singularity", "Sirius", "Sirius B", "Sol", "Solaris", "Sombrero", "Soul",
            "Spica", "Spindle", "Spiral Arm", "Stardust", "Starlight", "Stellar", "Sterope", "Styx",
            "Sudbury", "Suhail", "Sunflower", "Tabit", "Talitha", "Tania", "Tarazed", "Tartarus",
            "Tau Ceti", "Taygeta", "Teegarden", "Tegmine", "Tejat", "Tethys", "Thalassa", "Thanatos",
            "Theia", "Themis", "Theseus", "Thexantul", "Thuban", "Toliman", "Trappist-1", "Triangulum",
            "Trifid", "Tullifer", "Tureis", "Ultima Thule", "Uncharted", "Unknown Regions", "Unuk", "Upsilon Andromedae",
            "Uranus", "Vanguard", "Varuna", "Vega", "Veil", "Vela X-1", "Venan", "Venus",
            "Veritas", "Vesperia", "Vesta", "Vetas", "Void", "Void Sector", "Vorlag", "Vredefort",
            "Wezen", "Whirlpool", "Whisper", "White Dwarf", "Wild Space", "Wizard", "Wolf", "Wormhole",
            "X-47", "Xenon", "Xi Serpentis", "Xylos", "Yed", "Yildun", "Zaurak", "Zenith",
            "Zephyr", "Zerix", "Zeus", "Zubenelgenubi", "Zubeneschamali", "Zylon"
        ]
        
        self.corridor_names = [
            "Arc", "Artery", "Avenue", "Bend", "Breach", "Bridge", "Causeway", "Channel",
            "Chasm", "Circuit", "Conduit", "Corridor", "Course", "Cradle", "Crossing", "Cut",
            "Cylinder", "Divide", "Drift", "Flow", "Flux", "Fold", "Fork", "Freeway",
            "Gap", "Gateway", "Groove", "Highway", "Joint", "Junction", "Lane", "Lift",
            "Link", "Manor", "Merge", "Nerve", "Outlet", "Pass", "Passage", "Path",
            "Pipe", "Pull", "Push", "Ramp", "Reach", "Ribbon", "Ridge", "Route",
            "Run", "Seam", "Skein", "Slide", "Slip", "Sliptube", "Span", "Spindle",
            "Splice", "Spur", "Strait", "Strand", "Streamway", "Stretch", "Tether", "Thread",
            "Threadline", "Threadpath", "Threadway", "Throughway", "Trace", "Track", "Tract", "Trail",
            "Transit", "Traverse", "Trunk", "Vein", "Wane", "Way", "Weave"
        ]
        
        self.gate_names = [
            "Access Point", "Aligner", "Alignment Frame", "Anchor", "Anchor Frame", "Aperture", "Array", "Bridgehead",
            "Channel", "Clamp", "Conduit", "Connective Node", "Convergence", "Corridor Dock", "Coupler", "Cradle",
            "Entry", "Entry Point", "Fulcrum", "Gantry", "Gate", "Gateway", "Hardpoint", "Hub",
            "Inlet", "Interface", "Intersection", "Junction", "Keystone", "Link Point", "Lock", "Locus",
            "Manifold", "Maw", "Mount", "Nexus", "Nexus Arch", "Passage", "Perch", "Pillar",
            "Portal", "Pylon", "Routing Point", "Span", "Spine", "Stabilizer", "Staging Point", "Support Frame",
            "Terminal", "Threshold", "Transfer Node", "Transit Frame", "Transit Point", "Transit Ring", "Valve", "Vector Dock"
        ]
        self.galaxy_names = [
            "ABL-78I", "Acallaris Galaxy", "Acallaris Nebula", "Achernar Galaxy", "Acrux Galaxy", "Adhafera Galaxy", "Aether Drift", "Alcor Galaxy",
            "Alcyone Galaxy", "Alcyoneus Galaxy", "Aldebaran Galaxy", "Algieba Galaxy", "Algol Galaxy", "Alhena Galaxy", "Alioth Galaxy", "Aljanah Galaxy",
            "Alkaid Galaxy", "Almach Galaxy", "Alnair Galaxy", "Alnilam Galaxy", "Alpha Centauri Galaxy", "Alphard Galaxy", "Alpheratz Galaxy", "Alphirk Galaxy",
            "Alrakis Galaxy", "Alrescha Galaxy", "Aludra Galaxy", "Amphiaraus Galaxy", "Ancha Galaxy", "Andromeda Galaxy", "Andromeda I Dwarf Galaxy", "Andromeda II Dwarf Galaxy",
            "Andromeda III Dwarf Galaxy", "Andromedids Swirl", "Ankaa Galaxy", "Antares Galaxy", "Antennae Galaxies", "Apana Galaxy", "Apex Swirl", "Aquarius Void",
            "Aquila Rift", "Arcturus Galaxy", "Argo Nebulae", "Ascella Galaxy", "Asteropiaos Cloud", "Astraeus Cloud", "Atlas Galaxy", "Atria Galaxy",
            "Avior Galaxy", "Azelfafage Galaxy", "Azha Galaxy", "Baten Kaitos Galaxy", "Becrux Galaxy", "Beta Pictoris Galaxy", "Betelgeuse Galaxy", "Biham Galaxy",
            "Black Eye Galaxy", "Bode's Galaxy", "Boreas Stellar Collection", "Bo\u00c3\u00b6tes I Dwarf Galaxy", "Bo\u00c3\u00b6tes Void", "Bunda Galaxy", "Canis Major Dwarf Galaxy", "Canopus Galaxy",
            "Capella Galaxy", "Caph Galaxy", "Carina Dwarf Galaxy", "Castor Galaxy", "Celaeno Galaxy", "Celestia Cluster", "Centaurus A", "Cetus Dwarf Galaxy",
            "Chamaeleon Cloud", "Cigar Galaxy", "Coma Berenices Dwarf Galaxy", "Coma Supercluster", "Corona Borealis Galaxy", "Corona Borealis Supercluster", "Corvus Dark Anomaly", "Corvus Galaxy",
            "Cosmic Web", "Cosmos Prime", "Crawleb Cloud", "Crown Galaxy", "Crux Nemesi", "Crux-Centaurus Arm", "Cursa Galaxy", "Cygnus Arm",
            "Delta Aquariids Swirl", "Delta Draconis", "Delta Miriandynus", "Deneb Galaxy", "Denebola Galaxy", "Diphda Galaxy", "Dorado Rift", "Draco Dwarf Galaxy",
            "Draconids Stream", "Dubhe Galaxy", "ELT-45X Galaxy", "Ecliptic Rim", "Electra Galaxy", "Elnath Galaxy", "Eltanin Galaxy", "Enif Galaxy",
            "Eridanus Void", "Eta Aquariids Rift", "Euphorion Asteris", "Europa Nebula", "Euthenia", "Far 3KPC Arm", "Fomalhaut Galaxy", "Fornax Galaxy",
            "Furud Galaxy", "Gamma Borysthenis", "Gamma Dioscuri", "Geminids Swirl", "Gienah Galaxy", "Great Attractor", "Grus Galaxy", "HJ-315",
            "HV-232", "Hadar Galaxy", "Herculean Cluster", "Hercules Supercluster", "Heze Galaxy", "Homam Galaxy", "Hydor Galaxy", "Hydra-Centaurus Supercluster",
            "Hydrus Prime", "IC 1101", "Indus Swirl", "Iris Galaxy", "Izar Galaxy", "JKL 91B", "JL-08", "Jabbah Galaxy",
            "Kaffaljidhma Galaxy", "Kalypso Cluster", "Kaus Australis Galaxy", "Kentaurus Cloud", "Kitalpha Galaxy", "Kochab Galaxy", "Kornephoros Galaxy", "Kraz Galaxy",
            "LS 62C", "Lambda Eusebeia", "Laniakea Supercluster", "Leo I Dwarf Galaxy", "Leo II Dwarf Galaxy", "Leonids Cluster", "Local Arm", "Luminary Veil",
            "Lyra Polystratus", "Lyrids Veil", "Maia Galaxy", "Marfik Galaxy", "Markab Galaxy", "Menkalinan Galaxy", "Menkar Galaxy", "Mensa Halo",
            "Merak Galaxy", "Merope Galaxy", "Messier 81", "Messier 82", "Miaplacidus Galaxy", "Microscopium Nebula", "Milky Way Galaxy", "Mimosa Galaxy",
            "Mintaka Galaxy", "Mirfak Galaxy", "Mizar Galaxy", "Muliphein Galaxy", "NGC 1300", "NGC 6946", "Nadir Depths", "Nashira Galaxy",
            "Navi Galaxy", "Nemesis Cloud", "Nephele Cloud", "Nihal Galaxy", "Norma Arm", "Northern Local Void", "Nunki Galaxy", "OH 6K",
            "OIM-90G", "Octans Cluster", "Okul Galaxy", "Ophiuchus Spiral", "Orion Spur", "Orionids Galaxy", "Orions Cloud", "Outer Arm",
            "Pavo Kentaurus", "Peacock Galaxy", "Pegasus Dwarf Irregular Galaxy", "Peleus", "Peppura Cloud", "Perseids Cloud", "Perseus Arm", "Perseus-Pisces Supercluster",
            "Phoenicids Cluster", "Phoenix Dwarf Galaxy", "Pinwheel Galaxy", "Pisces Dwarf Galaxy", "Piscids Cluster", "Piscis Austrinus Void", "Pleione Galaxy", "Polaris Galaxy",
            "Pollux Galaxy", "Porrima Galaxy", "Procyon Galaxy", "Puppids-Velids Swirl", "Quadrantids Cloud", "RZ-369", "Rasalgethi Galaxy", "Rasalhague Galaxy",
            "Rastaban Galaxy", "Regulus Galaxy", "Reticulum Filament", "Rigel Galaxy", "Rotanev Galaxy", "Ruchbah Galaxy", "SH 68I", "Sabik Galaxy",
            "Sadalbari Galaxy", "Sadalmelik Galaxy", "Sadalsuud Galaxy", "Sagittarius Dwarf Irregular Galaxy", "Sagittarius Dwarf Spheroidal Galaxy", "Sagittarius Galactic Center", "Saiph Galaxy", "Sargas Galaxy",
            "Schedar Galaxy", "Scorpius Cloud", "Sculptor Dwarf Galaxy", "Sculptor Galaxy", "Scutum-Centaurus Arm", "Segue 1", "Segue 2", "Serpens Stellarstream",
            "Serpent Nebula", "Sextans Dwarf Galaxy", "Shapley Supercluster", "Shaula Galaxy", "Sirius Galaxy", "Sombrero Galaxy", "Southern Local Void", "Southern Pinwheel Galaxy",
            "Spica Galaxy", "Stardust Expanse", "Sterope Galaxy", "Suhail Galaxy", "Sunflower Galaxy", "TM-52", "TU-54", "Tabit Galaxy",
            "Talitha Galaxy", "Tania Australis Galaxy", "Tarazed Galaxy", "Taurids Cloud", "Taurus Void", "Taygeta Galaxy", "Tegmine Galaxy", "Tejat Galaxy",
            "Thuban Galaxy", "Triangulum Galaxy", "Triangulum II Dwarf Galaxy", "Tucana Dwarf Galaxy", "Tureis Galaxy", "UBV-67", "UH-033", "Unukalhai Galaxy",
            "Upsilon Alatheia", "Ursa Major Dwarf Galaxy", "Ursa Major II Dwarf Galaxy", "Ursa Minor Dwarf Galaxy", "Ursa Nebula", "Vega Galaxy", "Venan Gemini", "Virgo Arcturus",
            "Virgo Delta", "Volans Nexus", "Wezen Galaxy", "Whirlpool Galaxy", "Willman 1", "Yed Prior Galaxy", "Yildun Galaxy", "ZS-03",
            "Zagreus Galaxy", "Zaurak Galaxy", "Zenith Reach", "Zeta Arcturus", "Zubenelgenubi Galaxy", "Zubeneschamali Galaxy"
        ]
        
    def start_auto_shift_task(self):
        """Starts the auto shift task if not running."""
        if self.auto_shift_task is None or self.auto_shift_task.done():
            self.auto_shift_task = self.bot.loop.create_task(self._auto_corridor_shift_loop())
            print("🌌 Started automatic corridor shift task.")

    def stop_auto_shift_task(self):
        """Stops/Cancels the auto shift task."""
        if self.auto_shift_task and not self.auto_shift_task.done():
            self.auto_shift_task.cancel()
            print("🌌 Cancelled automatic corridor shift task.")
    
    def start_gate_check_task(self):
        """Starts the gate check task if not running."""
        if self.gate_check_task is None or self.gate_check_task.done():
            self.gate_check_task = self.bot.loop.create_task(self._gate_check_loop())
            print("🔄 Started gate reconnection check task.")
    
    def stop_gate_check_task(self):
        """Stops/Cancels the gate check task."""
        if self.gate_check_task and not self.gate_check_task.done():
            self.gate_check_task.cancel()
            print("🔄 Cancelled gate reconnection check task.")

    async def cog_load(self):
        """Called when the cog is loaded"""
        self.start_auto_shift_task()
        self.start_gate_check_task()
        
        # Check for moving gates on startup
        try:
            await self._check_and_reconnect_moving_gates()
            print("🔄 Checked for moving gates on startup")
        except Exception as e:
            print(f"⚠️ Error checking moving gates on startup: {e}")

    async def cog_unload(self):
        """Clean up background tasks when cog is unloaded"""
        self.stop_auto_shift_task()
        self.stop_gate_check_task()
            
    
    galaxy_group = app_commands.Group(name="galaxy", description="Galaxy generation and mapping")
    async def _auto_corridor_shift_loop(self):
        """Background task for automatic corridor shifts"""
        try:
            # Wait for bot to be ready
            await self.bot.wait_until_ready()
            
            # Initial delay before first shift (2-6 hours)
            initial_delay = random.randint(7200, 21600)  # 2-6 hours in seconds
            print(f"🌌 Auto corridor shifts will begin in {initial_delay//3600:.1f} hours")
            await asyncio.sleep(initial_delay)
            
            while not self.bot.is_closed():
                try:
                    # Check if galaxy exists with timeout protection
                    try:
                        location_count = await asyncio.wait_for(
                            asyncio.to_thread(
                                self.db.execute_query,
                                "SELECT COUNT(*) FROM locations",
                                fetch='one'
                            ),
                            timeout=10.0  # 10 second timeout
                        )
                        location_count = location_count[0] if location_count else 0
                    except asyncio.TimeoutError:
                        print("⚠️ Database query timeout in auto-shift, skipping this cycle")
                        await asyncio.sleep(3600)  # Wait 1 hour and try again
                        continue
                    except (RuntimeError, psycopg2.Error, psycopg2.OperationalError) as e:
                        print(f"⚠️ Database error in auto-shift: {e}")
                        await asyncio.sleep(3600)  # Wait 1 hour and try again
                        continue
                    except Exception as e:
                        print(f"⚠️ Unexpected error in auto-shift: {e}")
                        await asyncio.sleep(3600)  # Wait 1 hour and try again
                        continue
                    
                    if location_count > 0:
                        # Check for moving gates that need reconnection
                        await self._check_and_reconnect_moving_gates()
                        
                        await self._execute_automatic_shift()
                    
                    # Schedule next shift (6-24 hours)
                    next_shift = random.randint(21600, 86400)  # 6-24 hours
                    hours = next_shift / 3600
                    print(f"🌌 Next automatic corridor shift in {hours:.1f} hours")
                    await asyncio.sleep(next_shift)
                    
                except Exception as e:
                    print(f"❌ Error in auto corridor shift: {e}")
                    # Wait 30 minutes before trying again on error
                    await asyncio.sleep(1800)
                    
        except asyncio.CancelledError:
            print("🌌 Auto corridor shift task cancelled")
        except Exception as e:
            print(f"❌ Fatal error in auto corridor shift loop: {e}")

    async def _execute_automatic_shift(self):
        """Execute an automatic corridor shift"""
        try:
            # Random intensity (weighted toward lower values)
            intensity_weights = [0.4, 0.3, 0.2, 0.08, 0.02]  # Favor intensity 1-2
            intensity = random.choices(range(1, 6), weights=intensity_weights)[0]
            
            print(f"🌌 Executing automatic corridor shift (intensity {intensity})")
            
            results = await self._execute_corridor_shifts(intensity)
            
            # Log the results
            if results['activated'] or results['deactivated']:
                print(f"🌌 Auto-shift complete: +{results['activated']} routes, -{results['deactivated']} routes")
            
            # Check if we need to notify anyone
            if results['activated'] + results['deactivated'] >= 3:
                await self._broadcast_major_shift_alert(intensity, results)
            
            # Validate connectivity after shift
            connectivity_issues = await self._check_critical_connectivity_issues()
            if connectivity_issues:
                print(f"⚠️ Connectivity issues detected post-shift: {connectivity_issues}")
                # Auto-fix critical issues with validation
                max_fix_attempts = 3
                fix_attempt = 0
                
                while connectivity_issues and fix_attempt < max_fix_attempts:
                    try:
                        await self._auto_fix_critical_connectivity()
                        
                        # Validate the fix worked
                        if await self._validate_galaxy_connectivity():
                            print("✅ Connectivity issues resolved successfully")
                            break
                        else:
                            connectivity_issues = await self._check_critical_connectivity_issues()
                            fix_attempt += 1
                            print(f"⚠️ Fix attempt {fix_attempt} incomplete, retrying...")
                            
                    except Exception as fix_error:
                        fix_attempt += 1
                        import traceback
                        print(f"❌ Fix attempt {fix_attempt} failed: {fix_error}")
                        print(f"📋 Fix error details: {traceback.format_exc()}")
                        if fix_attempt >= max_fix_attempts:
                            print("⚠️ Maximum fix attempts reached, manual intervention may be required")
                            # Log current galaxy state for troubleshooting
                            try:
                                total_locations = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
                                active_corridors = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = true", fetch='one')[0]
                                dormant_corridors = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = false", fetch='one')[0]
                                print(f"🔍 Galaxy state: {total_locations} locations, {active_corridors} active corridors, {dormant_corridors} dormant corridors")
                            except Exception as state_error:
                                print(f"⚠️ Could not gather galaxy state: {state_error}")
                            break
        
        except Exception as e:
            import traceback
            print(f"❌ Error executing automatic shift: {e}")
            print(f"📋 Shift error details: {traceback.format_exc()}")
            # Log error context for debugging
            try:
                current_corridors = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = true", fetch='one')[0]
                print(f"🔍 Current active corridors: {current_corridors}")
            except Exception as context_error:
                print(f"⚠️ Could not gather error context: {context_error}")

    async def _broadcast_major_shift_alert(self, intensity: int, results: Dict):
        """Trigger news broadcast for major corridor shifts"""
        
        try:
            # Instead of sending to main channels, just call the news system
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                await news_cog.post_corridor_shift_news(results, intensity)
            print(f"🌌 Major shift broadcast triggered: +{results['activated']} routes, -{results['deactivated']} routes")
        except Exception as e:
            print(f"❌ Error in _broadcast_major_shift_alert: {e}")
            import traceback
            traceback.print_exc()
        
    async def _check_critical_connectivity_issues(self) -> str:
        """Check for critical connectivity issues that need immediate fixing"""
        
        locations = self.db.execute_query(
            "SELECT location_id FROM locations",
            fetch='all'
        )
        
        if not locations:
            return ""
        
        # Build connectivity graph
        graph = {loc[0]: set() for loc in locations}
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = true",
            fetch='all'
        )
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        # Check for critical issues
        issues = []
        
        # Multiple components (fragmentation)
        if len(components) > 1:
            largest = max(components, key=len)
            isolated_count = sum(len(comp) for comp in components if comp != largest)
            issues.append(f"{len(components)} disconnected clusters ({isolated_count} isolated locations)")
        
        # Locations with no connections
        no_connections = [loc_id for loc_id in graph if len(graph[loc_id]) == 0]
        if no_connections:
            issues.append(f"{len(no_connections)} completely isolated locations")
        
        return "; ".join(issues) if issues else ""

    async def _auto_fix_critical_connectivity(self):
        """Automatically fix critical connectivity issues"""
        print("🔧 Auto-fixing critical connectivity issues...")
        
        # Get all locations
        all_locations_data = self.db.execute_query(
            "SELECT location_id, name, location_type, x_coordinate, y_coordinate, wealth_level FROM locations",
            fetch='all'
        )
        
        # Convert to dict format
        all_locations = []
        for loc_id, name, loc_type, x, y, wealth in all_locations_data:
            all_locations.append({
                'id': loc_id,
                'name': name, 
                'type': loc_type,
                'x_coordinate': x,
                'y_coordinate': y,
                'wealth_level': wealth
            })
        
        # Find disconnected components
        graph = {loc['id']: set() for loc in all_locations}
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = true",
            fetch='all'
        )
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        if len(components) <= 1:
            return  # No fragmentation to fix
        
        # Connect all components to the largest one
        largest_component = max(components, key=len)
        fixes_applied = 0
        
        for component in components:
            if component == largest_component:
                continue
            
            # Find best connection between this component and largest
            best_distance = float('inf')
            best_corridor_id = None
            
            # First try to activate an existing dormant corridor
            for loc_id_a in component:
                for loc_id_b in largest_component:
                    dormant_corridor = self.db.execute_query(
                        "SELECT corridor_id FROM corridors WHERE origin_location = %s AND destination_location = %s AND is_active = false",
                        (loc_id_a, loc_id_b),
                        fetch='one'
                    )
                    
                    if dormant_corridor:
                        best_corridor_id = dormant_corridor[0]
                        break
                
                if best_corridor_id:
                    break
            
            # If found dormant corridor, activate it
            if best_corridor_id:
                self.db.execute_query(
                    "UPDATE corridors SET is_active = true WHERE corridor_id = %s",
                    (best_corridor_id,)
                )
                fixes_applied += 1
                print(f"🔧 Activated dormant corridor to reconnect isolated cluster")
            else:
                # Create new corridor as emergency measure
                component_locs = [loc for loc in all_locations if loc['id'] in component]
                largest_locs = [loc for loc in all_locations if loc['id'] in largest_component]
                
                # Find closest pair
                best_connection = None
                for loc_a in component_locs:
                    for loc_b in largest_locs:
                        distance = self._calculate_distance(loc_a, loc_b)
                        if distance < best_distance:
                            best_distance = distance
                            best_connection = (loc_a, loc_b)
                
                if best_connection and best_distance < 150:  # Don't create extremely long emergency corridors
                    loc_a, loc_b = best_connection
                    name = f"Emergency Link {loc_a['name']}-{loc_b['name']}"
                    fuel_cost = max(15, int(best_distance * 0.8) + 10)
                    danger = 4  # Emergency corridors are dangerous
                    travel_time = self._calculate_ungated_route_time(best_distance)
                    
                    # Create bidirectional emergency corridor atomically
                    emergency_conn = self.db.begin_transaction()
                    try:
                        result_1 = self.db.execute_in_transaction(
                            emergency_conn,
                            '''INSERT INTO corridors 
                               (name, origin_location, destination_location, travel_time, fuel_cost, 
                                danger_level, corridor_type, is_active, is_generated)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE) RETURNING corridor_id''',
                            (name, loc_a['id'], loc_b['id'], travel_time, fuel_cost, danger, 'ungated'),
                            fetch='one'
                        )
                        corridor_id_1 = result_1[0] if result_1 and len(result_1) > 0 else None
                        
                        result_2 = self.db.execute_in_transaction(
                            emergency_conn,
                            '''INSERT INTO corridors 
                               (name, origin_location, destination_location, travel_time, fuel_cost, 
                                danger_level, corridor_type, is_active, is_generated)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE) RETURNING corridor_id''',
                            (f"{name} Return", loc_b['id'], loc_a['id'], travel_time, fuel_cost, danger, 'ungated'),
                            fetch='one'
                        )
                        corridor_id_2 = result_2[0] if result_2 and len(result_2) > 0 else None
                        
                        # Validate both corridors were created
                        if not corridor_id_1 or not corridor_id_2:
                            raise Exception("Failed to create both directions of emergency corridor")
                        
                        self.db.commit_transaction(emergency_conn)
                    except Exception as corridor_error:
                        self.db.rollback_transaction(emergency_conn)
                        print(f"❌ Failed to create emergency corridor: {corridor_error}")
                        continue  # Skip this component, try next one
                    finally:
                        emergency_conn = None
                    
                    fixes_applied += 1
                    print(f"🆘 Created emergency corridor: {loc_a['name']} ↔ {loc_b['name']}")
        
        if fixes_applied > 0:
            print(f"🔧 Applied {fixes_applied} connectivity fixes")

    async def _validate_galaxy_connectivity(self) -> bool:
        """Validate critical galaxy connectivity constraints"""
        try:
            # Check for isolated locations
            all_locations = self.db.execute_query(
                "SELECT location_id FROM locations", fetch='all'
            )
            
            if not all_locations:
                return True  # No locations to validate
            
            # Build connectivity graph
            graph = {loc[0]: set() for loc in all_locations}
            active_corridors = self.db.execute_query(
                "SELECT origin_location, destination_location FROM corridors WHERE is_active = true",
                fetch='all'
            )
            
            for origin, dest in active_corridors:
                graph[origin].add(dest)
                graph[dest].add(origin)
            
            # Find connected components using DFS
            visited = set()
            components = []
            
            for loc_id in graph:
                if loc_id not in visited:
                    component = set()
                    stack = [loc_id]
                    
                    while stack:
                        current = stack.pop()
                        if current not in visited:
                            visited.add(current)
                            component.add(current)
                            stack.extend(graph[current] - visited)
                    
                    components.append(component)
            
            # Critical validation: no more than 1 major component
            # Allow small isolated components (1-2 locations) but not large ones
            major_components = [comp for comp in components if len(comp) > 2]
            
            if len(major_components) > 1:
                print(f"⚠️ Connectivity validation failed: {len(major_components)} major disconnected components")
                return False
            
            # Check for completely isolated major locations (not outposts)
            major_location_types = ['station', 'colony', 'colony_world']
            isolated_major = []
            
            for comp in components:
                if len(comp) == 1:  # Single isolated location
                    loc_id = list(comp)[0]
                    loc_type = self.db.execute_query(
                        "SELECT location_type FROM locations WHERE location_id = %s",
                        (loc_id,), fetch='one'
                    )
                    if loc_type and loc_type[0] in major_location_types:
                        isolated_major.append(loc_id)
            
            if isolated_major:
                print(f"⚠️ Connectivity validation failed: {len(isolated_major)} isolated major locations")
                return False
            
            print("✅ Galaxy connectivity validation passed")
            return True
            
        except Exception as e:
            print(f"❌ Error during connectivity validation: {e}")
            return False
    @galaxy_group.command(name="generate", description="Generate a new galaxy - THIS CAN TAKE A WHILE")
    @app_commands.describe(
        num_locations="Number of major locations to generate (10-500, random if not specified)",
        clear_existing="Whether to clear existing generated locations first",
        galaxy_name="Name for your galaxy (random if not specified)",
        start_date="Galaxy start date (DD-MM-YYYY format, random 2700-2799 if not specified)",
        debug_mode="Skip data clearing and use minimal generation for testing"
    )
    async def generate_galaxy(self, interaction: discord.Interaction, 
                             num_locations: int = None, 
                             clear_existing: bool = False,
                             galaxy_name: str = None,
                             start_date: str = None,
                             debug_mode: bool = False):
        # Initialize all variables at function start to prevent undefined variable errors
        major_locations = []
        gates = []
        corridors = []
        corridor_routes = []
        black_markets = 0
        federal_depots = 0
        total_homes = 0
        total_sub_locations = 0
        built_repeaters = 0
        log_books_created = 0
        total_history_events = 0
        conn = None  # Initialize database connection variable                     
        
        # Validate permissions first
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Debug mode overrides for testing
        if debug_mode:
            print("🔧 DEBUG MODE: Using minimal settings for testing")
            num_locations = 3  # Just a few locations for testing
            clear_existing = False  # Never clear in debug mode
            print(f"🔧 DEBUG: Set to {num_locations} locations, clear_existing={clear_existing}")
        
        # Validate and generate random values for unspecified parameters
        if num_locations is None:
            num_locations = random.randint(75, 150)
            print(f"🎲 Randomly selected {num_locations} locations to generate")
        elif num_locations < 10 or num_locations > 500:
            await interaction.response.send_message("Number of locations must be between 10 and 500.", ephemeral=True)
            return

        if galaxy_name is None:
            galaxy_name = random.choice(self.galaxy_names)
            print(f"🎲 Randomly selected galaxy name: {galaxy_name}")
        else:
            # Validate galaxy name
            if len(galaxy_name) > 100:
                await interaction.response.send_message("Galaxy name must be 100 characters or less.", ephemeral=True)
                return
            if not re.match(r'^[a-zA-Z0-9\s\-\'\.]+$', galaxy_name):
                await interaction.response.send_message("Galaxy name contains invalid characters. Use only letters, numbers, spaces, hyphens, apostrophes, and periods.", ephemeral=True)
                return

        if start_date is None:
            # Generate random date between 2700-2799
            year = random.randint(2700, 2799)
            month = random.randint(1, 12)
            # Handle different days per month
            if month in [1, 3, 5, 7, 8, 10, 12]:
                day = random.randint(1, 31)
            elif month in [4, 6, 9, 11]:
                day = random.randint(1, 30)
            else:  # February
                day = random.randint(1, 28)
            start_date = f"{day:02d}-{month:02d}-{year}"
            print(f"🎲 Randomly selected start date: {start_date}")
        
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        try:
            if re.match(r'^\d{4}$', start_date):
                start_date_obj = datetime(int(start_date), 1, 1)
                start_date = f"01-01-{start_date}"
            elif re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', start_date):
                start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            else:
                raise ValueError("Invalid date format")
        except ValueError:
            await interaction.response.send_message("Invalid date format. Use DD-MM-YYYY or YYYY.", ephemeral=True)
            return

        if not (2700 <= start_date_obj.year <= 2799):
            await interaction.response.send_message("Start date year must be between 2700 and 2799.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        progress_msg = await interaction.followup.send("🌌 **Galaxy Generation Started**\n⏳ Pausing background tasks...", ephemeral=True)
        
        # Stop ALL background tasks with proper coordination
        print("🛑 Stopping all background tasks with coordination...")
        
        # Collect all tasks that need to be stopped
        tasks_to_stop = []
        
        # Stop main bot background tasks
        try:
            self.bot.stop_background_tasks()
            print("🛑 Requested stop for main bot tasks")
        except Exception as e:
            print(f"⚠️ Error stopping main bot tasks: {e}")

        # Stop status updater specifically and wait for it
        status_updater_cog = self.bot.get_cog('StatusUpdaterCog')
        if status_updater_cog and hasattr(status_updater_cog, 'update_status_channels'):
            try:
                task_loop = status_updater_cog.update_status_channels
                if task_loop.is_running():
                    task_loop.cancel()
                    # Give it time to actually stop
                    for _ in range(10):  # Wait up to 1 second
                        if not task_loop.is_running():
                            break
                        await asyncio.sleep(0.1)
                    print("🛑 Status updater stopped")
                else:
                    print("🛑 Status updater was not running")
            except Exception as e:
                print(f"⚠️ Error stopping status updater: {e}")

        # Stop channel manager background tasks specifically
        channel_manager = getattr(self.bot, 'channel_manager', None)
        if channel_manager:
            channel_manager.auto_cleanup_enabled = False
            print("🛑 Disabled channel manager auto-cleanup")

        # Stop any cog-specific tasks
        events_cog = self.bot.get_cog('EventsCog')
        if events_cog and hasattr(events_cog, 'stop_all_tasks'):
            try:
                events_cog.stop_all_tasks()
                print("🛑 Requested stop for events cog tasks")
            except Exception as e:
                print(f"⚠️ Error stopping events cog tasks: {e}")

        # Stop our own corridor shift task if running
        if self.auto_shift_task and not self.auto_shift_task.done():
            self.auto_shift_task.cancel()
            try:
                await asyncio.wait_for(self.auto_shift_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            print("🛑 Stopped corridor shift task")

        # Final coordination delay with progress feedback
        print("🛑 Allowing tasks to complete shutdown...")
        await asyncio.sleep(1.0)
        print("✅ Background task shutdown coordination complete")
        
        # Variables already initialized at function start
        
        try:
            # Phase 1: Galaxy setup and locations (single transaction)
            print("🔧 DEBUG: Starting Phase 1 - Beginning transaction...")
            import time
            start_time = time.time()
            conn = self.db.begin_transaction()
            print(f"🔧 DEBUG: Transaction started successfully in {time.time() - start_time:.2f}s")
            try:
                print("🔧 DEBUG: Updating progress message...")
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🗑️ Setting up galaxy...")
                print("🔧 DEBUG: Progress message updated")
                
                # Galaxy info and clearing
                print("🔧 DEBUG: Inserting galaxy info...")
                current_time = datetime.now()
                self.db.execute_in_transaction(conn,
                    """INSERT INTO galaxy_info 
                       (galaxy_id, name, start_date, time_scale_factor, time_started_at, is_time_paused, current_ingame_time) 
                       VALUES (1, %s, %s, 4.0, %s, false, %s)
                       ON CONFLICT (galaxy_id) DO UPDATE SET 
                       name = EXCLUDED.name,
                       start_date = EXCLUDED.start_date,
                       time_scale_factor = EXCLUDED.time_scale_factor,
                       time_started_at = EXCLUDED.time_started_at,
                       is_time_paused = EXCLUDED.is_time_paused,
                       current_ingame_time = EXCLUDED.current_ingame_time""",
                    (galaxy_name, start_date, current_time.isoformat(), start_date_obj.isoformat())
                )
                print("🔧 DEBUG: Galaxy info inserted successfully")
                
                if clear_existing:
                    print("🔧 DEBUG: Starting to clear existing galaxy data...")
                    await self._clear_existing_galaxy_data(conn)
                    print("🔧 DEBUG: Finished clearing existing galaxy data")
                await asyncio.sleep(0.5)
                print("🔧 DEBUG: About to update progress for major locations...")
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🏭 Creating major locations...")
                print("🔧 DEBUG: Starting major location generation...")
                major_locations = await self._generate_major_locations(conn, num_locations, start_date_obj.year)
                print(f"🔧 DEBUG: Generated {len(major_locations)} major locations")
                
                # Cleanup memory after major location generation
                self._cleanup_large_arrays()
                print("🧹 Memory cleanup completed after location generation")
                
                print("🔧 DEBUG: Committing transaction...")
                self.db.commit_transaction(conn)
                conn = None
                print("🔧 DEBUG: Transaction committed successfully")
            except Exception as e:
                print(f"🔧 DEBUG: Exception in Phase 1: {e}")
                if conn:
                    print("🔧 DEBUG: Rolling back transaction...")
                    self.db.rollback_transaction(conn)
                raise
            
            # Allow other coroutines to run after transaction completion
            await asyncio.sleep(0.1)
                
            # Phase 2: Routes and infrastructure (separate transactions to avoid locks)
            try:
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🛣️ Planning active corridor routes...")
                corridor_routes = await self._plan_corridor_routes(major_locations)
                
                if not corridor_routes:
                    print("⚠️ No corridor routes generated, creating emergency connections...")
                    # Create at least one route to prevent complete isolation
                    if len(major_locations) >= 2:
                        corridor_routes = [{
                            'from': major_locations[0],
                            'to': major_locations[1], 
                            'importance': 'critical',
                            'distance': self._calculate_distance(major_locations[0], major_locations[1])
                        }]
                
                await asyncio.sleep(0.1)
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🚪 Generating transit gates...")
                gates = await self._generate_gates_for_routes(None, corridor_routes, major_locations)
                
                all_locations = major_locations + gates
                await asyncio.sleep(0.1)
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🌉 Creating active corridor network...")
                corridors = await self._create_corridors(None, corridor_routes, all_locations)
                
                # Data written successfully to PostgreSQL
                await asyncio.sleep(1.0)

            except Exception as e:
                print(f"❌ Error in Phase 2: {e}")
                raise
                
            if 'all_locations' not in locals():
                # Ensure gates is defined, fallback to empty list if not
                if 'gates' not in locals():
                    gates = []
                    print("⚠️ Gates not defined due to Phase 2 error, using empty list")
                all_locations = major_locations + gates
                print(f"📍 Defined all_locations: {len(major_locations)} major + {len(gates)} gates = {len(all_locations)} total")
                
            # Allow other tasks to run
            await asyncio.sleep(0.5)
            
            # Phase 3: Additional features (separate transaction with better yielding)
            conn = self.db.begin_transaction()
            try:
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🎭 Establishing facilities...")
                black_markets = await self._generate_black_markets(conn, major_locations)
                federal_depots = await self._assign_federal_supplies(conn, major_locations)
                
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🏢 Creating infrastructure...")
                total_sub_locations = await self._generate_sub_locations_for_all_locations(conn, all_locations)
                
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n📡 Installing systems...")
                built_repeaters = await self._generate_built_in_repeaters(conn, all_locations)
                
                # Commit this transaction before log generation
                self.db.commit_transaction(conn)
                conn = None
                print("✅ Phase 3 transaction committed")
                await asyncio.sleep(1.0)

                # Generate logs in separate transaction
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n📜 Creating location log books...")
                try:
                    # Don't pass a connection since _generate_initial_location_logs manages its own
                    log_books_created = await self._generate_initial_location_logs(None, all_locations, start_date_obj)
                except Exception as e:
                    print(f"⚠️ Log generation failed: {e}")
                    log_books_created = 0  # Continue even if log generation fails
                
                # Brief pause before dormant corridor generation
                await asyncio.sleep(0.1)
                
                try:
                    # Generate dormant corridors (this now handles its own transactions)
                    await progress_msg.edit(content="🌌 **Galaxy Generation**\n🌫️ Creating dormant corridors...")
                    if corridor_routes:  # Only if we have active routes
                        await self._create_dormant_corridors(None, all_locations, corridor_routes)
                        print("✅ Dormant corridor generation completed")
                        # Clean up memory after intensive corridor generation
                        self._cleanup_large_arrays()
                        print("🧹 Memory cleanup completed after dormant corridor generation")
                    else:
                        print("⚠️ Skipping dormant corridors - no active routes to base them on")
                    
                    await asyncio.sleep(1.0)
                    
                except Exception as dormant_error:
                    print(f"⚠️ Dormant corridor generation failed: {dormant_error}")
                    print("   Continuing with galaxy generation...")
                
                await asyncio.sleep(1.0)

            except Exception as e:
                if conn:
                    try:
                        self.db.rollback_transaction(conn)
                        print("🔧 Rolled back Phase 3 transaction due to error")
                    except Exception as rollback_error:
                        print(f"⚠️ Error during Phase 3 rollback: {rollback_error}")
                    finally:
                        conn = None
                raise
                
            await asyncio.sleep(0.5)
            
            # Phase 4: NPC Generation (completely outside any transaction)
            await progress_msg.edit(content="🌌 **Galaxy Generation**\n🤖 Populating with inhabitants...")

            print("✅ Database consistency maintained before NPC generation")

            # Now generate NPCs without any active transactions
            await self._create_npcs_outside_transaction(all_locations, progress_msg)

            # Brief yield before history generation
            await asyncio.sleep(0.1)
            
            # Step 8: Generate homes for colonies and space stations
            await progress_msg.edit(content="🌌 **Galaxy Generation**\n🏠 Creating residential properties...")
            total_homes = await self._generate_homes_for_locations(major_locations)
            
            # Post-generation tasks (outside transactions)
            npc_cog = self.bot.get_cog('NPCCog')
            if npc_cog:
                await npc_cog.spawn_initial_dynamic_npcs()

            # Generate history outside transaction to avoid deadlock
            if debug_mode:
                print("🔧 DEBUG MODE: Skipping history generation for faster testing")
                total_history_events = 0
            else:
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n📚 Documenting galactic history...")
                history_gen = HistoryGenerator(self.bot)
                total_history_events = 0
                try:
                    # Perform database readiness check before history generation
                    print("🔧 Checking database readiness for history generation...")
                    await self._ensure_database_ready_for_history()
                    
                    print("🔧 Starting optimized history generation...")
                    total_history_events = await history_gen.generate_galaxy_history(start_date_obj.year, start_date_obj.strftime('%Y-%m-%d'))
                    print(f"🔧 History generation completed successfully with {total_history_events} events")
                except Exception as history_e:
                    print(f"⚠️ History generation failed: {history_e}")
                    print("🔧 Galaxy generation will continue without historical events")
                    total_history_events = 0
                    # Don't raise - allow galaxy generation to complete without history

            await progress_msg.edit(content="🌌 **Galaxy Generation**\n✅ **Generation Complete!**")

        except Exception as e:
            print(f"❌ Error during galaxy generation: {e}")
            import traceback
            traceback.print_exc()
            # Ensure any open connection is cleaned up
            if conn:
                try:
                    self.db.rollback_transaction(conn)
                    print("🔧 Rolled back any open transaction due to error")
                except Exception as rollback_error:
                    print(f"⚠️ Error during rollback: {rollback_error}")
                finally:
                    conn = None
            # Continue to try sending an embed even if generation partially failed
        
        finally:
            # Ensure database connections are cleaned up in all cases
            if conn:
                try:
                    self.db.rollback_transaction(conn)
                    print("🔧 Cleaned up connection in finally block")
                except Exception as cleanup_error:
                    print(f"⚠️ Error during connection cleanup: {cleanup_error}")
                finally:
                    conn = None
            
            # Restart background tasks to ensure they always restart regardless of generation outcome
            try:
                await progress_msg.edit(content="🔄 **Galaxy Generation**\n🔄 Resuming background tasks...")
                # Longer delay before restarting
                await asyncio.sleep(2.0)

                # Restart background tasks
                print("🔄 Restarting background tasks...")
                self.bot.start_background_tasks()

                status_updater_cog = self.bot.get_cog('StatusUpdaterCog')
                if status_updater_cog:
                    # Check if the task exists and use correct Loop methods
                    if hasattr(status_updater_cog, 'update_status_channels'):
                        task_loop = status_updater_cog.update_status_channels
                        # Use is_running() instead of done() for discord.ext.tasks.Loop
                        if not task_loop.is_running():
                            try:
                                task_loop.restart()
                                print("🔄 Restarted status updater")
                            except Exception as restart_error:
                                print(f"⚠️ Could not restart status updater: {restart_error}")
                        else:
                            print("🔄 Status updater already running")
                    else:
                        print("⚠️ Status updater task not found")

                # Re-enable channel manager cleanup
                channel_manager = getattr(self.bot, 'channel_manager', None)
                if channel_manager:
                    channel_manager.auto_cleanup_enabled = True
                    print("🔄 Re-enabled channel manager auto-cleanup")
            except Exception as restart_error:
                print(f"❌ Error restarting background tasks: {restart_error}")

        # MOVED: Embed creation and sending outside of try blocks with safe defaults
        try:
            # Ensure all variables are properly defined with safe defaults
            total_locations_generated = len(major_locations) + len(gates)
            total_infrastructure = total_locations_generated

            # Add randomization info
            randomized_info = []
            if num_locations is None:
                randomized_info.append("Number of locations")
            if galaxy_name is None:
                randomized_info.append("Galaxy name")
            if start_date is None:
                randomized_info.append("Start date")

            randomized_text = f"\n*Randomly generated: {', '.join(randomized_info)}*" if randomized_info else ""

            # Create and send the embed
            embed = discord.Embed(
                title=f"🌌 {galaxy_name} - Creation Complete",
                description=f"Successfully generated {total_locations_generated} major locations plus {len(gates)} transit gates ({total_infrastructure} total infrastructure) and {len(corridors)} corridors.\n**Galactic Era Begins:** {start_date_obj.strftime('%d-%m-%Y')} 00:00 ISST{randomized_text}",
                color=0x00ff00
            )

            # Count major location types safely
            location_counts = {'colony': 0, 'space_station': 0, 'outpost': 0}
            for loc in major_locations:
                location_counts[loc['type']] += 1

            location_text = "\n".join([f"{t.replace('_', ' ').title()}s: {c}" for t, c in location_counts.items()])
            location_text += f"\n**Total Major Locations: {total_locations_generated}**"
            location_text += f"\nTransit Gates: {len(gates)} (additional infrastructure)"
            if black_markets > 0:
                location_text += f"\nBlack Markets: {black_markets} (outlaw)"
            if federal_depots > 0:
                location_text += f"\nFederal Supply Depots: {federal_depots} (government)"

            embed.add_field(name="Infrastructure Generated", value=location_text, inline=True)

            # Count corridor types safely
            gated_routes = len([r for r in corridor_routes if r.get('has_gates', False)])
            ungated_routes = len(corridor_routes) - gated_routes
            estimated_corridors = (gated_routes * 6) + (ungated_routes * 2)
            corridor_text = f"Total Routes: {len(corridor_routes)}\nGated Routes (Safe): {gated_routes}\nUngated Routes (Risky): {ungated_routes}\nTotal Corridor Segments: {estimated_corridors}"
            embed.add_field(name="Corridor Network", value=corridor_text, inline=True)

            embed.add_field(name="", value="", inline=True)  # Spacer

            embed.add_field(
                name="⏰ Inter-Solar Standard Time (ISST)",
                value=f"**Galaxy Start:** {start_date} 00:00 ISST\n**Time Scale:** 4x speed (6 hours real = 1 day in-game)\n**Status:** ✅ Active",
                inline=False
            )

            embed.add_field(
                name="📅 Historical Timeline",
                value=f"Galaxy Start Date: {start_date_obj.strftime('%d-%m-%Y')}\nIn-game time flows at 4x speed\nUse `/date` to check current galactic time",
                inline=False
            )
            
            embed.add_field(
                name="🏠 Residential Properties",
                value=f"{total_homes} homes generated",
                inline=True
            )

            # Ensure galactic news channel is configured and send connection announcement
            await self._ensure_galactic_news_setup(interaction.guild, galaxy_name)

            # Send the success embed
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as embed_error:
            # If embed creation fails, send a simple success message
            print(f"❌ Error creating success embed: {embed_error}")
            try:
                await interaction.followup.send(
                    f"✅ **Galaxy Generation Complete!**\n"
                    f"Galaxy '{galaxy_name}' has been successfully generated.\n"
                    f"Generated {len(major_locations)} major locations with transit infrastructure.\n"
                    f"Start date: {start_date_obj.strftime('%d-%m-%Y')} 00:00 ISST", 
                    ephemeral=True
                )
            except Exception as fallback_error:
                print(f"❌ Error sending fallback message: {fallback_error}")


    async def _create_earth(self, conn, start_year: int) -> Dict[str, Any]:
        """Creates the static Earth location within a transaction."""
        print("🔧 DEBUG: _create_earth starting...")
        description = (
            "Earth still exists but is a hollowed-out symbol more than a paradise. Centuries of overuse, industrial exploitation, "
            "and political decay have rendered the planet nearly unable to system natural ecosystems. It supports its population "
            "consisting of a shrinking bureaucratic core and the wealthy only through imports from its colonies, yet its ability to govern or support "
            "those colonies is minimal. Some colonies remain loyal out of habit or necessity; others are functionally independent, and some actively oppose "
            "Earth's influence, which now functions more like inertia than active control."
        )
        print("🔧 DEBUG: Creating Earth location data...")
        location = {
            'name': "Earth", 'type': 'colony', 'x_coordinate': 0, 'y_coordinate': 0,
            'system_name': "Sol", 'description': description, 'wealth_level': 10,
            'population': random.randint(50000, 100000),
            'established_date': f"{start_year - 4000}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            'has_jobs': True, 'has_shops': True, 'has_medical': True, 'has_repairs': True,
            'has_fuel': True, 'has_upgrades': True, 'has_black_market': False,
            'is_generated': True, 'is_derelict': False, 'has_shipyard': True
        }
        print("🔧 DEBUG: Saving Earth to database...")
        location_id = self._save_location_to_db(conn, location)
        print(f"🔧 DEBUG: Earth saved with ID {location_id}")
        
        # Validate Earth location ID
        if location_id is None or location_id <= 0:
            error_msg = f"❌ Failed to create Earth location: invalid ID {location_id}"
            print(error_msg)
            raise ValueError(error_msg)
            
        location['id'] = location_id
        print("🌍 Created static location: Earth in Sol system.")
        return location
    async def _create_npcs_outside_transaction(self, all_locations: List[Dict], progress_msg=None):
        """Create NPCs with better transaction isolation"""
        npc_cog = self.bot.get_cog('NPCCog')
        if not npc_cog:
            print("❌ NPCCog not found, skipping NPC creation.")
            return
        
        total_npcs_created = 0
        batch_size = 50  # Smaller batches
        current_batch = []
        
        # Pre-fetch all location data to avoid queries during generation
        location_data_map = {}
        for location in all_locations:
            location_data_map[location['id']] = {
                'population': location.get('population', 100),
                'type': location['type'],
                'wealth_level': location['wealth_level'],
                'has_black_market': location.get('has_black_market', False),
                'is_derelict': location.get('is_derelict', False)
            }
        
        for i, location in enumerate(all_locations):
            if progress_msg and i % 10 == 0:
                percent_complete = (i / len(all_locations)) * 100
                await progress_msg.edit(
                    content=f"🌌 **Galaxy Generation**\n🤖 Populating with inhabitants... ({percent_complete:.0f}%)"
                )
                # Yield control
                await asyncio.sleep(0.05)
            
            # Skip NPC generation for derelict locations
            if location_data_map[location['id']]['is_derelict']:
                continue
                
            # Get NPC data without database calls
            npc_data_list = npc_cog.generate_static_npc_batch_data(
                location['id'],
                location_data_map[location['id']]['population'],
                location_data_map[location['id']]['type'],
                location_data_map[location['id']]['wealth_level'],
                location_data_map[location['id']]['has_black_market'],
                location_data_map[location['id']]['is_derelict']
            )
            
            current_batch.extend(npc_data_list)
            
            # Insert batch when it reaches size limit
            if len(current_batch) >= batch_size:
                # Use a completely new connection for each batch
                try:
                    # Direct insert without transaction wrapper
                    self.db.execute_query(
                        '''INSERT INTO static_npcs 
                           (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                        current_batch,
                        many=True
                    )
                    
                    total_npcs_created += len(current_batch)
                    print(f"🤖 Created {len(current_batch)} static NPCs (total: {total_npcs_created})...")
                    current_batch = []
                    
                    # Longer yield between batches
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"❌ Error creating NPC batch: {e}")
                    current_batch = []  # Clear failed batch
                    await asyncio.sleep(0.5)  # Wait before continuing
        
        # Insert remaining NPCs
        if current_batch:
            try:
                self.db.execute_query(
                    '''INSERT INTO static_npcs 
                       (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    current_batch,
                    many=True
                )
                total_npcs_created += len(current_batch)
            except Exception as e:
                print(f"❌ Error creating final NPC batch: {e}")
        
        print(f"🤖 Total NPCs created: {total_npcs_created}")
    
    def _cleanup_large_arrays(self):
        """Clear large arrays from memory to prevent buildup"""
        import gc
        
        # Clear any large class-level arrays that might have accumulated
        # (The location name arrays are static and should not be cleared)
        
        # Force garbage collection to reclaim memory from temporary variables
        before_count = len(gc.get_objects())
        gc.collect()
        after_count = len(gc.get_objects())
        
        if before_count - after_count > 1000:  # Only log significant cleanups
            print(f"🧹 Memory cleanup: freed {before_count - after_count} objects")
            
    def _cleanup_large_variables(self, **local_vars):
        """Clean up large local variables to free memory"""
        import gc
        
        # Identify large data structures
        large_vars_to_clear = []
        for name, value in local_vars.items():
            if isinstance(value, (list, dict, set)):
                if len(value) > 1000:  # Arbitrary threshold for "large"
                    large_vars_to_clear.append(name)
                    
        if large_vars_to_clear:
            print(f"🧹 Clearing large variables: {', '.join(large_vars_to_clear)}")
            
        # Clear the variables
        for name in large_vars_to_clear:
            if name in local_vars:
                local_vars[name].clear() if hasattr(local_vars[name], 'clear') else None
                
        # Force garbage collection
        gc.collect()
        
    async def _generate_major_locations(self, conn, num_locations: int, start_year: int) -> List[Dict]:
        """Generate colonies, space stations, and outposts within a transaction."""
        print(f"🔧 DEBUG: Starting _generate_major_locations with {num_locations} locations")
        distributions = {'colony': 0.30, 'space_station': 0.35, 'outpost': 0.40}
        major_locations = []
        used_names = set()
        used_systems = set()

        print("🔧 DEBUG: Creating Earth location...")
        earth_location = await self._create_earth(conn, start_year)
        print(f"🔧 DEBUG: Earth location created: {earth_location.get('name', 'Unknown')}")
        major_locations.append(earth_location)
        used_names.add(earth_location['name'])
        used_systems.add(earth_location['system_name'])

        print(f"🔧 DEBUG: Starting loop to create {num_locations - 1} additional locations...")
        for i in range(num_locations - 1):  # -1 because Earth is included
            if i % 10 == 0:
                print(f"🔧 DEBUG: Creating location {i+1}/{num_locations-1}")
            
            loc_type = random.choices(list(distributions.keys()), list(distributions.values()))[0]
            name = self._generate_unique_name(loc_type, used_names)
            used_names.add(name)
            system = self._generate_unique_system(used_systems)
            used_systems.add(system)

            establishment_year = start_year - random.randint(5, 350)
            establishment_date = f"{establishment_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
            
            print(f"🔧 DEBUG: Creating location data for {name}...")
            location_data = self._create_location_data(name, loc_type, system, establishment_date)
            print(f"🔧 DEBUG: Saving location {name} to database...")
            location_id = self._save_location_to_db(conn, location_data)
            print(f"🔧 DEBUG: Location {name} saved with ID {location_id}")
            
            # Validate the location ID before adding to major_locations
            if location_id is None or location_id <= 0:
                error_msg = f"❌ Failed to create location {name}: invalid ID {location_id}"
                print(error_msg)
                continue  # Skip this location instead of crashing
                
            location_data['id'] = location_id
            major_locations.append(location_data)
            
            # Yield control every 10 locations
            if i % 10 == 0:
                await asyncio.sleep(0)
        
        print(f"🔧 DEBUG: _generate_major_locations completed, created {len(major_locations)} locations")        
        return major_locations
    async def _create_npcs_for_galaxy(self, conn):
        """Creates NPCs for all locations within the transaction."""
        npc_cog = self.bot.get_cog('NPCCog')
        if not npc_cog:
            print("❌ NPCCog not found, skipping NPC creation.")
            return

        # Get location data needed for NPC generation
        all_locations = self.db.execute_in_transaction(conn,
            "SELECT location_id, population, location_type, wealth_level, has_black_market, is_derelict FROM locations",
            fetch='all'
        )
        
        npcs_to_insert = []
        locations_processed = 0
        
        for loc_id, pop, loc_type, wealth, has_black_market, is_derelict in all_locations:
            # Skip NPC generation for derelict locations
            if is_derelict:
                continue
                
            # Pass all required data to avoid database calls within the method
            npc_data_list = npc_cog.generate_static_npc_batch_data(
                loc_id, pop, loc_type, wealth, has_black_market, is_derelict
            )
            npcs_to_insert.extend(npc_data_list)
            locations_processed += 1
            
            # Batch insert every 50 locations to avoid memory issues
            if locations_processed % 50 == 0:
                if npcs_to_insert:
                    query = '''INSERT INTO static_npcs 
                               (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
                    self.db.executemany_in_transaction(conn, query, npcs_to_insert)
                    print(f"🤖 Created {len(npcs_to_insert)} static NPCs (batch {locations_processed // 50})...")
                    npcs_to_insert = []  # Clear the list
                
                # Yield control to event loop
                await asyncio.sleep(0)
        
        # Insert any remaining NPCs
        if npcs_to_insert:
            query = '''INSERT INTO static_npcs 
                       (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
            self.db.executemany_in_transaction(conn, query, npcs_to_insert)
            print(f"🤖 Created {len(npcs_to_insert)} static NPCs (final batch).")
    
    async def _generate_black_markets(self, conn, major_locations: List[Dict]) -> int:
        """
        Enhanced black market generation using the proper item system from item_config.py
        """
        from utils.item_config import ItemConfig
        
        # Input validation
        if not major_locations:
            print("⚠️ No major locations provided for black market generation")
            return 0
            
        print(f"🔍 Starting black market generation for {len(major_locations)} locations")
        
        black_markets_created = 0
        locations_to_flag = []
        items_to_insert = []

        # Get black market appropriate items from the proper item system
        def get_black_market_items():
            """Get items appropriate for black markets"""
            black_market_items = []
            
            # Medical items (illegal/unregulated)
            medical_items = ItemConfig.get_items_by_type("medical")
            for item in medical_items:
                item_data = ItemConfig.get_item_definition(item)
                if item_data.get("rarity") in ["uncommon", "rare"]:  # Harder to get legally
                    black_market_items.append((item, "medical", "Unregulated medical supplies"))
            
            # Equipment items (illegal/modified)
            equipment_items = ItemConfig.get_items_by_type("equipment")
            for item in equipment_items:
                item_data = ItemConfig.get_item_definition(item)
                if item_data.get("rarity") in ["rare", "legendary"]:  # Military/restricted
                    black_market_items.append((item, "equipment", "Military surplus or stolen equipment"))
            
            # Upgrade items (illegal modifications)
            upgrade_items = ItemConfig.get_items_by_type("upgrade")
            for item in upgrade_items:
                black_market_items.append((item, "upgrade", "Unlicensed ship modifications"))
            
            # Special black market exclusives (add to ItemConfig.py)
            exclusive_items = [
                ("Forged Transit Papers", "documents", "Fake identification documents"),
                ("Identity Scrubber", "service", "Erases identity records - illegal but effective"),
                ("Stolen Data Chips", "data", "Information of questionable origin"),
                ("Unmarked Credits", "currency", "Untraceable digital currency"),
                ("Weapon System Override", "software", "Bypasses weapon safety protocols"),
                ("Neural Interface Hack", "software", "Illegal consciousness enhancement"),
            ]
            black_market_items.extend(exclusive_items)
            
            return black_market_items

        black_market_item_pool = get_black_market_items()

        # Debug: Log location data structure for troubleshooting
        print(f"🔍 DEBUG: Examining location data structure:")
        for i, location in enumerate(major_locations[:3]):  # Show first 3 locations
            print(f"  Location {i}: keys={list(location.keys())}, id={location.get('id', 'MISSING')}, name={location.get('name', 'MISSING')}")

        for location in major_locations:
            # Input validation to prevent foreign key constraint violations
            if not location or 'id' not in location or location['id'] is None or location['id'] <= 0:
                print(f"⚠️ Skipping black market generation for invalid location: {location}")
                continue
                
            black_market_chance = 0.0
            
            # Enhanced spawn logic (as before)
            if location['wealth_level'] <= 2:
                black_market_chance = 0.35
            elif location['wealth_level'] <= 3:
                black_market_chance = 0.25
            elif location['wealth_level'] <= 4:
                black_market_chance = 0.15
            elif location['wealth_level'] == 5:
                black_market_chance = 0.08
            elif location['wealth_level'] == 6:
                black_market_chance = 0.03
            
            # Location type modifiers
            if location['type'] == 'outpost':
                black_market_chance *= 1.5
            elif location['type'] == 'space_station':
                black_market_chance *= 0.7
            elif location['type'] == 'colony':
                black_market_chance *= 1.0
            
            # Population modifiers
            if location['population'] < 100:
                black_market_chance *= 1.3
            elif location['population'] > 1000:
                black_market_chance *= 0.8
                
            if location.get('is_derelict', False):
                black_market_chance = 0.60
            
            black_market_chance = min(black_market_chance, 0.60)
            
            if black_market_chance > 0 and random.random() < black_market_chance:
                
                market_type = 'underground' if location['wealth_level'] <= 2 else 'discrete'
                reputation_required = random.randint(0, 2) if location['wealth_level'] <= 2 else random.randint(1, 4)
                
                try:
                    result = self.db.execute_in_transaction(
                        conn,
                        '''INSERT INTO black_markets (location_id, market_type, reputation_required, is_hidden)
                           VALUES (%s, %s, %s, true) RETURNING market_id''',
                        (location['id'], market_type, reputation_required),
                        fetch='one'
                    )
                    market_id = result[0] if result and len(result) > 0 else None
                except Exception as e:
                    print(f"❌ Failed to create black market for location {location.get('name', 'Unknown')} (ID: {location.get('id', 'None')}): {e}")
                    continue
                
                if market_id:
                    black_markets_created += 1
                    locations_to_flag.append((location['id'],))
                    
                    # Generate items using proper item system
                    item_count = random.randint(3, 6)
                    selected_items = random.sample(black_market_item_pool, min(item_count, len(black_market_item_pool)))
                    
                    for item_name, item_type, description in selected_items:
                        # Get proper item data if it exists in ItemConfig
                        item_data = ItemConfig.get_item_definition(item_name)
                        
                        if item_data:
                            # Use ItemConfig pricing with black market markup
                            base_price = item_data.get("base_value", 100)
                            markup_multiplier = random.uniform(1.5, 3.0)  # 50-200% markup
                            final_price = int(base_price * markup_multiplier)
                            stock = 1 if item_data.get("rarity") in ["rare", "legendary"] else random.randint(1, 3)
                        else:
                            # Fallback for exclusive items
                            final_price = random.randint(1000, 5000)
                            stock = random.randint(1, 2)
                        
                        items_to_insert.append(
                            (market_id, item_name, item_type, final_price, stock, description)
                        )
                    
                    print(f"🕴️  Created {market_type} black market at {location['name']}")

        # Bulk database operations
        if locations_to_flag:
            self.db.executemany_in_transaction(
                conn,
                "UPDATE locations SET has_black_market = TRUE WHERE location_id = %s",
                locations_to_flag
            )
        
        if items_to_insert:
            # Update the black_market_items table to include stock
            self.db.executemany_in_transaction(
                conn,
                '''INSERT INTO black_market_items (market_id, item_name, item_type, price, stock, item_description)
                   VALUES (%s, %s, %s, %s, %s, %s)''',
                items_to_insert
            )
            
        return black_markets_created
        
    async def _safe_transaction_wrapper(self, operation_name: str, operation_func, *args, **kwargs):
        """Safely execute database operations with proper error handling"""
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                result = await operation_func(*args, **kwargs)
                return result
            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Database locked during {operation_name}, retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"❌ Error in {operation_name}: {e}")
                    raise
                    
    def _create_location_data(self, name: str, loc_type: str, system: str, establishment_date: str) -> Dict:
        """Create location data with varied and flavorful descriptions"""
        import random, math

        # Generate coordinates in a galaxy-like distribution
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(10, 90)
        
        # Add spiral arm effect
        spiral_factor = radius / 90.0
        angle += spiral_factor * math.pi * 0.5
        
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        
        # Determine base properties by type
        # Check for derelict status first (5% chance)
        is_derelict = random.random() < 0.05

        if is_derelict:
            # Derelict locations have very low wealth and population
            wealth = 0
            population = 0
            description = self._generate_derelict_description(name, loc_type, system, establishment_date)
        else:
            # Normal location generation
            if loc_type == 'colony':
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(80, 500) * (wealth + 2)
                description = self._generate_colony_description(name, system, establishment_date, wealth, population)
            elif loc_type == 'space_station':
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(50, 350) * wealth
                description = self._generate_station_description(name, system, establishment_date, wealth, population)
            elif loc_type == 'gate':
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(3, 15)
                description = self._generate_station_description(name, system, establishment_date, wealth, population)
            else:  # outpost
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(5, 50)
                description = self._generate_outpost_description(name, system, establishment_date, wealth, population)
        
        # Build the dict with derelict-aware defaults
        if is_derelict:
            # Derelict locations have minimal or no services
            loc = {
                'name': name,
                'type': loc_type,
                'x_coordinate': x,
                'y_coordinate': y,
                'system_name': system,
                'description': description,
                'wealth_level': wealth,
                'population': population,
                'established_date': establishment_date,
                'has_jobs': False,
                'has_shops': False,
                'has_medical': False,
                'has_repairs': False,
                'has_fuel': False,   
                'has_upgrades': False,
                'has_shipyard': False,
                'has_federal_supplies': False,
                'has_black_market': False,
                'is_generated': True,
                'is_derelict': True
            }
        else:
            # Normal location defaults
            loc = {
                'name': name,
                'type': loc_type,
                'x_coordinate': x,
                'y_coordinate': y,
                'system_name': system,
                'description': description,
                'wealth_level': wealth,
                'population': population,
                'established_date': establishment_date,
                'has_jobs': True,
                'has_shops': True,
                'has_medical': True,
                'has_repairs': True,
                'has_fuel': True,
                'has_upgrades': False,
                'has_shipyard': False,
                'has_federal_supplies': False,
                'has_black_market': False,
                'is_generated': True,
                'is_derelict': False
            }
        
        # Apply random service removals
        if loc_type == 'colony' and random.random() < 0.10:
            loc['has_jobs'] = False
        if loc_type == 'outpost' and random.random() < 0.20:
            loc['has_shops'] = False
        if loc_type == 'space_station' and random.random() < 0.05:
            loc['has_medical'] = False
        if loc_type == 'space_station' and wealth >= 7:
            loc['has_shipyard'] = random.random() < 0.45  # 45% chance for wealthy stations
        elif loc_type == 'colony' and wealth >= 5:
            loc['has_shipyard'] = random.random() < 0.45  # 45% chance for medium or higher wealth colonies
        else:
            loc['has_shipyard'] = False
        return loc
    def _generate_derelict_description(self, name: str, location_type: str, system: str, establishment_date: str) -> str:
        """Generate descriptions for abandoned/derelict locations"""
        year = establishment_date[:4] if establishment_date else "unknown"
        
        if location_type == 'colony':
            openings = [
                f"The abandoned {name} colony drifts silent in {system}, its lights long since extinguished since {year}.",
                f"Once a thriving settlement, {name} now stands as a haunting monument to failed dreams in {system}.",
                f"Derelict since catastrophe struck in {year}, {name} colony remains a ghost town in {system}.",
                f"The skeletal remains of {name} colony cling to life support, its population fled from {system}.",
            ]
        elif location_type == 'space_station':
            openings = [
                f"The derelict {name} station tumbles slowly through {system}, its corridors echoing with memories of {year}.",
                f"Emergency power barely keeps {name} station from becoming space debris in {system}.",
                f"Abandoned since {year}, {name} station serves as a grim reminder of {system}'s dangers.",
                f"The gutted hulk of {name} drifts powerless through {system}, atmosphere leaking into the void.",
            ]
        else:  # outpost
            openings = [
                f"The deserted {name} outpost barely maintains life support in the hostile {system} frontier.",
                f"Long abandoned, {name} outpost stands as a lonely beacon of failure in {system}.",
                f"The automated systems of {name} continue their lonely vigil in {system} since {year}.",
                f"Stripped and abandoned, {name} outpost offers only shelter from {system}'s unforgiving void.",
            ]
        
        conditions = [
            "Scavenged equipment lies scattered throughout the facility.",
            "Emergency life support operates on backup power with failing systems.",
            "Makeshift repairs hold together what looters haven't already taken.",
            "Automated distress beacons still broadcast on abandoned frequencies.",
            "Hull breaches sealed with emergency patches tell stories of desperation.",
            "The few remaining inhabitants live like ghosts among the ruins."
        ]
        
        return f"{random.choice(openings)} {random.choice(conditions)}"
    def _generate_colony_description(self, name: str, system: str, establishment_date: str, wealth: int, population: int) -> str:
        """Generate varied colony descriptions based on wealth and character"""
        year = establishment_date[:4]
        
        # Opening templates based on wealth and character
        if wealth >= 7:  # Wealthy colonies
            openings = [
                f"The prosperous colony of {name} dominates the {system} system, its gleaming spires visible from orbit since {year}.",
                f"{name} stands as a crown jewel of human expansion in {system}, established {year} during the great colonial boom.",
                f"Renowned throughout the sector, {name} has been the economic heart of {system} since its founding in {year}.",
                f"The influential {name} colony commands respect across {system}, its wealth evident in every polished surface since {year}.",
                f"Since {year}, {name} has transformed from a modest settlement into {system}'s premier colonial destination."
            ]
        elif wealth >= 4:  # Average colonies
            openings = [
                f"The steady colony of {name} has weathered {system}'s challenges since its establishment in {year}.",
                f"Founded in {year}, {name} serves as a reliable anchor point in the {system} system.",
                f"{name} colony has grown methodically since {year}, becoming an integral part of {system}'s infrastructure.",
                f"Established {year}, {name} represents the determined spirit of {system} system colonization.",
                f"The industrious settlement of {name} has maintained steady growth in {system} since {year}."
            ]
        else:  # Poor colonies
            openings = [
                f"The struggling colony of {name} barely clings to survival in the harsh {system} system since {year}.",
                f"Founded in {year} during harder times, {name} endures the daily challenges of life in {system}.",
                f"{name} colony scratches out a meager existence in {system}, its founders' {year} dreams long faded.",
                f"The frontier outpost of {name} has survived against the odds in {system} since {year}.",
                f"Established {year}, {name} remains a testament to human stubbornness in the unforgiving {system} system."
            ]
        
        # Specialization and character details
        specializations = []
        
        if wealth >= 6:
            specializations.extend([
                "Its advanced hydroponics bays produce exotic foods exported across the sector.",
                "Massive automated factories churn out precision components for starship construction.",
                "The colony's renowned research facilities attract scientists from across human space.",
                "Gleaming residential towers house workers in climate-controlled luxury.",
                "State-of-the-art mining operations extract rare minerals from the system's asteroids.",
                "Its prestigious academy trains the next generation of colonial administrators.",
                "Sophisticated atmospheric processors maintain perfect environmental conditions.",
                "The colony's cultural centers showcase the finest arts from across the frontier."
            ])
        elif wealth >= 3:
            specializations.extend([
                "Sprawling agricultural domes provide essential food supplies for the region.",
                "Its workshops produce reliable tools and equipment for neighboring settlements.",
                "The colony's medical facilities serve patients from across the system.",
                "Modest but efficient factories manufacture basic goods for local trade.",
                "Its transportation hub connects remote outposts throughout the system.",
                "The settlement's technical schools train skilled workers for the colonial workforce.",
                "Basic atmospheric processing keeps the colony's air breathable and stable.",
                "Local markets bustle with traders from throughout the system."
            ])
        else:
            specializations.extend([
                "Makeshift shelters cobbled from salvaged ship parts house the struggling population.",
                "Its jury-rigged life support systems require constant maintenance to function.",
                "The colony's single cantina serves as meeting hall, market, and social center.",
                "Desperate miners work dangerous claims hoping to strike it rich.",
                "Patched atmospheric domes leak precious air into the void of space.",
                "The settlement's workshop repairs anything for anyone willing to pay.",
                "Its ramshackle structures huddle together against the system's harsh environment.",
                "Basic hydroponics barely provide enough nutrition to keep colonists alive."
            ])
        
        # Environmental and atmospheric details
        environments = []
        
        if population > 2000:
            environments.extend([
                "Streets teem with activity as thousands go about their daily business.",
                "The colony's districts each maintain their own distinct character and culture.",
                "Public transport systems efficiently move citizens between residential and work areas.",
                "Multiple shifts ensure the colony operates continuously around the clock."
            ])
        elif population > 500:
            environments.extend([
                "The community maintains a close-knit atmosphere where everyone knows their neighbors.",
                "Well-worn paths connect the various sections of the growing settlement.",
                "Regular town meetings in the central plaza keep citizens informed and involved.",
                "The colony's compact layout makes everything accessible within a short walk."
            ])
        else:
            environments.extend([
                "Every resident plays multiple roles to keep the small community functioning.",
                "The tight-knit population faces each challenge together as an extended family.",
                "Simple prefab structures cluster around the central life support facility.",
                "Harsh conditions forge unbreakable bonds between the hardy colonists."
            ])
        
        # Combine elements
        opening = random.choice(openings)
        specialization = random.choice(specializations)
        environment = random.choice(environments)
        
        return f"{opening} {specialization} {environment}"

    def _generate_station_description(self, name: str, system: str, establishment_date: str, wealth: int, population: int) -> str:
        """Generate varied space station descriptions"""
        year = establishment_date[:4]
        
        # Station type and opening based on wealth
        if wealth >= 8:  # Premium stations
            openings = [
                f"The magnificent {name} orbital complex has served as {system}'s premier space facility since {year}.",
                f"Gleaming in {system}'s starlight, {name} station represents the pinnacle of orbital engineering since {year}.",
                f"The prestigious {name} facility has commanded {system}'s spacelanes since its construction in {year}.",
                f"Since {year}, {name} has stood as the crown jewel of {system}'s orbital infrastructure.",
                f"The luxurious {name} station has catered to the sector's elite since its inauguration in {year}."
            ]
        elif wealth >= 5:  # Standard stations
            openings = [
                f"The reliable {name} orbital platform has anchored {system}'s space traffic since {year}.",
                f"Established {year}, {name} station serves as a crucial waypoint in the {system} system.",
                f"The sturdy {name} facility has weathered {system}'s challenges since its construction in {year}.",
                f"Since {year}, {name} has maintained steady operations in {system}'s orbital space.",
                f"The practical {name} station fulfills its role in {system} with quiet efficiency since {year}."
            ]
        else:  # Budget stations
            openings = [
                f"The aging {name} station barely maintains operations in {system} since its rushed construction in {year}.",
                f"Built on a shoestring budget in {year}, {name} somehow keeps functioning in {system}.",
                f"The patchwork {name} facility cobbles together services for {system} travelers since {year}.",
                f"Since {year}, {name} has scraped by on minimal funding in the {system} system.",
                f"The no-frills {name} station provides basic services to {system} with stubborn persistence since {year}."
            ]
        
        # Station functions and features
        functions = []
        
        if wealth >= 7:
            functions.extend([
                "Its premium docking bays accommodate the largest luxury liners and corporate vessels.",
                "Exclusive shopping promenades offer rare goods from across human space.",
                "The station's diplomatic quarters host high-level negotiations between star systems.",
                "State-of-the-art laboratories conduct cutting-edge research in zero gravity.",
                "Luxurious entertainment districts provide refined pleasures for wealthy travelers.",
                "Advanced medical facilities offer treatments unavailable on planetary surfaces.",
                "The station's concert halls feature renowned performers from across the galaxy.",
                "Private quarters rival the finest hotels on any core world."
            ])
        elif wealth >= 4:
            functions.extend([
                "Standard docking facilities efficiently handle routine cargo and passenger traffic.",
                "The station's markets provide essential supplies for ships and crews.",
                "Its maintenance bays offer reliable repairs for most classes of spacecraft.",
                "Central administration coordinates shipping schedules throughout the system.",
                "The facility's recreational areas help travelers unwind between journeys.",
                "Medical stations provide standard healthcare for spacers and visitors.",
                "Its communications arrays relay messages across the system's trade networks.",
                "Cargo holds temporarily store goods in transit between distant worlds."
            ])
        else:
            functions.extend([
                "Cramped docking clamps barely accommodate visiting ships safely.",
                "The station's single cantina doubles as marketplace and meeting hall.",
                "Its makeshift repair bay handles emergency fixes with salvaged parts.",
                "A skeleton crew keeps critical life support and docking systems operational.",
                "Basic sleeping quarters offer little more than a bunk and storage locker.",
                "The station's medical bay consists of a first aid kit and prayer.",
                "Jury-rigged communications equipment sometimes connects to the outside galaxy.",
                "Cargo areas serve double duty as additional living space when needed."
            ])
        
        # Operational details
        operations = []
        
        if population > 5000:
            operations.extend([
                "Multiple shifts ensure the massive facility operates continuously.",
                "Thousands of workers maintain the complex's countless systems and services.",
                "The station's districts each specialize in different aspects of space commerce.",
                "Advanced automation handles routine tasks while humans focus on complex decisions."
            ])
        elif population > 1000:
            operations.extend([
                "A dedicated crew keeps all essential systems running smoothly.",
                "The station's compact design allows efficient movement throughout the facility.",
                "Department heads coordinate closely to maintain optimal operations.",
                "Regular maintenance schedules keep the aging infrastructure functional."
            ])
        else:
            operations.extend([
                "A small but determined crew performs multiple duties to keep operations running.",
                "Every person aboard plays crucial roles in the station's survival.",
                "Makeshift solutions and creative repairs keep the facility marginally operational.",
                "The skeleton crew works around the clock to maintain basic services."
            ])
        
        opening = random.choice(openings)
        function = random.choice(functions)
        operation = random.choice(operations)
        
        return f"{opening} {function} {operation}"
    async def _find_route_to_destination(self, start_location_id: int, end_location_id: int, max_jumps: int = 5) -> Optional[List[int]]:
        """
        Finds a route between two locations using a Breadth-First Search (BFS) algorithm.
        Returns a list of location_ids representing the path, or None if no path is found within max_jumps.
        """
        if start_location_id == end_location_id:
            return [start_location_id]

        # Fetch all active corridors to build the graph
        corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = true",
            fetch='all'
        )

        graph = {}
        for origin, dest in corridors:
            if origin not in graph:
                graph[origin] = []
            if dest not in graph:
                graph[dest] = []
            graph[origin].append(dest)
            graph[dest].append(origin) # Assuming bidirectional corridors for pathfinding

        # BFS initialization
        queue = collections.deque([(start_location_id, [start_location_id])])
        visited = {start_location_id}

        while queue:
            current_location, path = queue.popleft()

            if current_location == end_location_id:
                return path

            if len(path) - 1 >= max_jumps: # Check jump limit
                continue

            for neighbor in graph.get(current_location, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [neighbor]
                    queue.append((neighbor, new_path))
        
        return None # No path found
    def _generate_outpost_description(self, name: str, system: str, establishment_date: str, wealth: int, population: int) -> str:
        """Generate varied outpost descriptions"""
        year = establishment_date[:4]
        
        # Outpost character based on wealth
        if wealth >= 4:  # Well-funded outposts
            openings = [
                f"The well-equipped {name} outpost has monitored {system}'s frontier since {year}.",
                f"Established {year}, {name} serves as a reliable beacon in the {system} system's remote reaches.",
                f"The strategic {name} facility has maintained its watch over {system} since {year}.",
                f"Since {year}, {name} has provided essential services to {system}'s far-flung territories.",
                f"The efficient {name} outpost has safeguarded {system}'s periphery since its establishment in {year}."
            ]
        else:  # Basic outposts
            openings = [
                f"The isolated {name} outpost clings to existence in {system}'s hostile frontier since {year}.",
                f"Built from necessity in {year}, {name} barely maintains a foothold in the {system} system.",
                f"The remote {name} facility has endured {system}'s challenges through determination since {year}.",
                f"Since {year}, {name} has scraped by on the edge of civilization in {system}.",
                f"The hardy {name} outpost refuses to surrender to {system}'s unforgiving environment since {year}."
            ]
        
        # Purpose and function
        purposes = []
        
        if wealth >= 3:
            purposes.extend([
                "Its sensor arrays provide early warning of corridor shifts and spatial anomalies.",
                "The outpost's communication relay connects isolated settlements to the wider galaxy.",
                "Well-stocked supply depot offers emergency provisions to stranded travelers.",
                "Its research station monitors local stellar phenomena and space weather.",
                "The facility serves as a customs checkpoint for traffic entering the system.",
                "Emergency medical facilities provide critical care for spacers in distress.",
                "Its maintenance shop handles urgent repairs for ships damaged in transit.",
                "The outpost's staff coordinates search and rescue operations throughout the region."
            ])
        else:
            purposes.extend([
                "A basic radio beacon helps lost ships find their way to safety.",
                "The outpost's fuel depot provides emergency refueling for desperate travelers.",
                "Its small workshop attempts repairs with whatever spare parts are available.",
                "Emergency shelters offer minimal protection from the system's harsh environment.",
                "The facility's medical kit treats injuries when no other help is available.",
                "Basic atmospheric processors maintain breathable air for the tiny crew.",
                "Its food supplies stretch to feed unexpected visitors in emergencies.",
                "The outpost serves as a final waypoint before entering the deep frontier."
            ])
        
        # Living conditions and atmosphere
        conditions = []
        
        if population > 30:
            conditions.extend([
                "The expanded crew maintains professional standards despite their isolation.",
                "Regular supply runs keep the outpost well-stocked and connected to civilization.",
                "Multiple shifts ensure someone is always monitoring the frontier zones.",
                "The facility's rec room provides essential social space for the resident staff."
            ])
        elif population > 10:
            conditions.extend([
                "A tight-knit crew has formed an almost familial bond over years of isolation.",
                "The small team rotates duties to prevent anyone from feeling overwhelmed.",
                "Shared meals and stories help maintain morale through the long watches.",
                "Everyone pulls together when emergencies strike the remote facility."
            ])
        else:
            conditions.extend([
                "A lone operator or tiny crew maintains the facility through sheer determination.",
                "The isolation weighs heavily on those who choose to serve in such remote postings.",
                "Every supply delivery is a major event breaking the endless routine.",
                "The skeleton crew relies on automation to handle most routine tasks."
            ])
        
        opening = random.choice(openings)
        purpose = random.choice(purposes)
        condition = random.choice(conditions)
        
        return f"{opening} {purpose} {condition}"

        self.db.execute_query(
            '''INSERT INTO locations 
               (name, location_type, description, wealth_level, population,
                x_coordinate, y_coordinate, system_name, established_date, has_jobs, has_shops, has_medical, 
                has_repairs, has_fuel, has_upgrades, has_black_market, is_generated, is_derelict) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (location['name'], location['type'], location['description'], 
             location['wealth_level'], location['population'], location['x_coordinate'], 
             location['y_coordinate'], location['system_name'], location['established_date'],
             location['has_jobs'], location['has_shops'], location['has_medical'], 
             location['has_repairs'], location['has_fuel'], location['has_upgrades'],
             location['has_black_market'], location['is_generated'], location['is_derelict'])
        )
            
        return self.db.execute_query(
            "SELECT location_id FROM locations WHERE name = %s ORDER BY location_id DESC LIMIT 1",
            (location['name'],),
            fetch='one'
        )[0]
        
    async def _assign_federal_supplies(self, conn, major_locations: List[Dict]) -> int:
        """
        Enhanced federal supply depot assignment with actual item implementation
        """
        from utils.item_config import ItemConfig
        
        locations_to_update = []
        federal_items_to_insert = []
        
        # Define what federal depots actually offer
        def get_federal_supply_items():
            """Get items that federal depots should stock"""
            federal_items = []
            
            # High-quality medical supplies
            medical_items = ItemConfig.get_items_by_type("medical")
            for item in medical_items:
                federal_items.append((item, "medical", "Federal medical supplies"))
            
            # Military-grade equipment
            equipment_items = ItemConfig.get_items_by_type("equipment") 
            for item in equipment_items:
                item_data = ItemConfig.get_item_definition(item)
                if item_data.get("rarity") in ["uncommon", "rare"]:
                    federal_items.append((item, "equipment", "Military surplus equipment"))
            
            # Premium fuel
            fuel_items = ItemConfig.get_items_by_type("fuel")
            for item in fuel_items:
                federal_items.append((item, "fuel", "Federal fuel reserves"))
            
            # Authorized upgrades
            upgrade_items = ItemConfig.get_items_by_type("upgrade")
            for item in upgrade_items:
                federal_items.append((item, "upgrade", "Authorized ship modifications"))
            
            # Federal exclusives
            exclusive_items = [
                ("Federal ID Card", "documents", "Official federal identification"),
                ("Military Rations", "consumable", "High-quality preserved food"),
                ("Federal Comm Codes", "data", "Access to federal communication networks"),
                ("Loyalty Certification", "documents", "Proof of federal allegiance"),
                ("Federal Permit", "documents", "Authorization for restricted activities"),
            ]
            federal_items.extend(exclusive_items)
            
            return federal_items

        federal_item_pool = get_federal_supply_items()

        for location in major_locations:
            federal_chance = 0.0
            
            # Enhanced spawn logic (as before)
            if location['wealth_level'] >= 9:
                federal_chance = 0.40
            elif location['wealth_level'] >= 8:
                federal_chance = 0.30
            elif location['wealth_level'] >= 7:
                federal_chance = 0.20
            elif location['wealth_level'] == 6:
                federal_chance = 0.12
            elif location['wealth_level'] == 5:
                federal_chance = 0.05
            
            # Location type modifiers
            if location['type'] == 'space_station':
                federal_chance *= 1.4
            elif location['type'] == 'colony':
                federal_chance *= 1.0
            elif location['type'] == 'outpost':
                federal_chance *= 0.6
                
            # Population modifiers
            if location['population'] > 2000:
                federal_chance *= 1.3
            elif location['population'] > 1000:
                federal_chance *= 1.1
            elif location['population'] < 200:
                federal_chance *= 0.7
                
            # Special cases
            if location['name'] == 'Earth':
                federal_chance = 1.0
                
            if location.get('has_black_market', False) or location.get('is_derelict', False):
                federal_chance = 0.0
            
            if location['name'] != 'Earth':
                federal_chance = min(federal_chance, 0.50)
            
            if federal_chance > 0 and random.random() < federal_chance:
                gets_shipyard = location.get('has_shipyard', False)
                if not gets_shipyard and location['wealth_level'] >= 8:
                    gets_shipyard = random.random() < 0.8
                elif not gets_shipyard and location['wealth_level'] >= 6:
                    gets_shipyard = random.random() < 0.5
                    
                locations_to_update.append((
                    True,  # has_federal_supplies
                    True,  # has_upgrades
                    gets_shipyard,  # has_shipyard
                    location['id']
                ))
                
                # Generate federal supply items
                item_count = random.randint(4, 8)  # Federal depots are well-stocked
                selected_items = random.sample(federal_item_pool, min(item_count, len(federal_item_pool)))
                
                for item_name, item_type, description in selected_items:
                    item_data = ItemConfig.get_item_definition(item_name)
                    
                    if item_data:
                        # Federal pricing - slight discount from base value
                        base_price = item_data.get("base_value", 100)
                        federal_discount = random.uniform(0.8, 0.9)  # 10-20% discount
                        final_price = int(base_price * federal_discount)
                        stock = random.randint(3, 8)  # Well-stocked
                    else:
                        # Exclusive items
                        final_price = random.randint(500, 2000)
                        stock = random.randint(2, 5)
                    
                    federal_items_to_insert.append(
                        (location['id'], item_name, item_type, final_price, stock, description, "federal", False)
                    )
                
                print(f"🏛️  Created federal depot at {location['name']}")
        
        # Database operations
        if locations_to_update:
            update_query = """UPDATE locations SET 
                                has_federal_supplies = %s, 
                                has_upgrades = %s, 
                                has_shipyard = %s 
                              WHERE location_id = %s"""
            self.db.executemany_in_transaction(conn, update_query, locations_to_update)
        
        # Insert federal supply items into shop_items table with federal tag
        if federal_items_to_insert:
            self.db.executemany_in_transaction(
                conn,
                '''INSERT INTO shop_items (location_id, item_name, item_type, price, stock, description, metadata, sold_by_player)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                federal_items_to_insert
            )
            
        return len(locations_to_update)
        
    def update_location_alignment_rules(self):
        """Update locations to enforce alignment-based spawning rules"""
        
        # Mark high-wealth locations as federal/loyal zones
        self.db.execute_query(
            """UPDATE locations 
               SET has_federal_supplies = true 
               WHERE wealth_level >= 8 AND has_black_market = false""",
        )
        
        # Mark low-wealth black market locations as bandit zones  
        self.db.execute_query(
            """UPDATE locations 
               SET has_black_market = true 
               WHERE wealth_level <= 3 AND has_federal_supplies = false AND random() < 0.1""",
        )
        
        print("✅ Updated location alignment rules")

    def enforce_npc_alignment_at_location(self, location_id: int):
        """Ensure NPCs at a location match its alignment requirements"""
        
        # Get location requirements
        location_data = self.db.execute_query(
            """SELECT has_black_market, has_federal_supplies, wealth_level 
               FROM locations WHERE location_id = %s""",
            (location_id,),
            fetch='one'
        )
        
        if not location_data:
            return
        
        has_black_market, has_federal_supplies, wealth_level = location_data
        
        # Determine required alignment
        required_alignment = None
        if has_black_market:
            required_alignment = "bandit"
        elif has_federal_supplies or wealth_level >= 8:
            required_alignment = "loyal"
        
        if required_alignment:
            # Update static NPCs to match required alignment
            wrong_npcs = self.db.execute_query(
                """SELECT npc_id FROM static_npcs 
                   WHERE location_id = %s AND alignment != %s AND is_alive = true""",
                (location_id, required_alignment),
                fetch='all'
            )
            
            for (npc_id,) in wrong_npcs:
                # Kill wrong-aligned NPCs and schedule respawn with correct alignment
                self.db.execute_query(
                    "UPDATE static_npcs SET is_alive = false WHERE npc_id = %s",
                    (npc_id,)
                )
                
                # Schedule respawn with correct alignment
                respawn_time = datetime.now() + timedelta(minutes=random.randint(30, 120))
                self.db.execute_query(
                    """INSERT INTO npc_respawn_queue 
                       (original_npc_id, location_id, scheduled_respawn_time, npc_data)
                       VALUES (%s, %s, %s, %s)""",
                    (npc_id, location_id, respawn_time.isoformat(), f"alignment:{required_alignment}")
                )
            
            # Update dynamic NPCs that shouldn't be here
            self.db.execute_query(
                """UPDATE dynamic_npcs 
                   SET current_location = NULL, destination_location = NULL
                   WHERE current_location = %s AND alignment != %s AND is_alive = true""",
                (location_id, required_alignment)
            )
    # =================================================================================
    # OPTIMIZED CORRIDOR PLANNING (REPLACEMENT FOR _plan_corridor_routes and helpers)
    # =================================================================================

# In _plan_corridor_routes method, replace the existing method with proper variable handling:

    async def _plan_corridor_routes(self, major_locations: List[Dict]) -> List[Dict]:
        """
        Plans logical corridor routes with improved connectivity and performance for large galaxies.
        This optimized version uses a spatial grid to accelerate proximity searches,
        avoiding O(n^2) complexity issues that cause hangs.
        """
        if not major_locations:
            return []

        num_locs = len(major_locations)
        print(f"🛣️ Planning routes for {num_locs} locations using spatial grid optimization...")
        
        # Progress reporting for large galaxies
        if num_locs > 200:
            print(f"📊 Large galaxy detected - route planning may take several minutes")

        # Step 0: Create the spatial grid for efficient lookups.
        grid_size = 75
        spatial_grid = self._create_spatial_grid(major_locations, grid_size)
        location_map = {loc['id']: loc for loc in major_locations}
        
        # Use a set to track created connections (as pairs of sorted IDs) to avoid duplicates.
        connected_pairs = set()
        routes = []
        
        # Progress tracking for user feedback
        import time
        start_time = time.time()

        # Step tracking variables
        total_steps = 5
        current_step = 0

        # Step 1: Create a Minimum Spanning Tree (MST) to ensure base connectivity.
        current_step += 1
        step_start = time.time()
        print("  - Step 1/5: Building Minimum Spanning Tree...")
        mst_routes = await self._create_mst_optimized(major_locations, location_map, connected_pairs)
        routes.extend(mst_routes)
        
        # Progress reporting
        step_time = time.time() - step_start
        print(f"  ✓ Step 1/5 complete - {len(mst_routes)} MST routes created in {step_time:.1f}s")
        
        # Yield control
        await asyncio.sleep(0.1)
            
        # Step 2: Add hub connections (stations to high-value colonies).
        current_step += 1
        step_start = time.time()
        print("  - Step 2/5: Creating hub connections...")
        hub_routes = await self._create_hub_connections_optimized(major_locations, location_map, spatial_grid, grid_size, connected_pairs)
        routes.extend(hub_routes)
        
        # Progress reporting
        step_time = time.time() - step_start
        print(f"  ✓ Step 2/5 complete - {len(hub_routes)} hub routes created in {step_time:.1f}s")
        
        # Yield control
        await asyncio.sleep(0.1)
            
        # Step 3: Add redundant connections for resilience.
        current_step += 1
        step_start = time.time()
        print("  - Step 3/5: Adding redundant connections...")
        redundant_routes = await self._add_redundant_connections_optimized(major_locations, location_map, spatial_grid, grid_size, connected_pairs)
        routes.extend(redundant_routes)
        
        # Progress reporting
        step_time = time.time() - step_start
        print(f"  ✓ Step 3/5 complete - {len(redundant_routes)} redundant routes created in {step_time:.1f}s")
        
        # Yield control
        await asyncio.sleep(0.1)
            
        # Step 4: Create long-range "bridge" connections to link distant regions.
        current_step += 1
        step_start = time.time()
        print("  - Step 4/5: Forging long-range bridges...")
        bridge_routes = await self._create_regional_bridges_optimized(major_locations, location_map, spatial_grid, connected_pairs)
        routes.extend(bridge_routes)
        
        # Progress reporting
        step_time = time.time() - step_start
        print(f"  ✓ Step 4/5 complete - {len(bridge_routes)} bridge routes created in {step_time:.1f}s")
        
        # Yield control
        await asyncio.sleep(0.1)
            
        # Step 5: Final validation and fixing of any isolated clusters.
        current_step += 1
        step_start = time.time()
        print("  - Step 5/5: Validating and fixing connectivity...")
        final_routes = await self._validate_and_fix_connectivity_optimized(major_locations, routes, location_map)
        
        # Final progress reporting
        total_time = time.time() - start_time
        step_time = time.time() - step_start
        print(f"  ✓ Step 5/5 complete - connectivity validated in {step_time:.1f}s")
        print(f"✅ Route planning complete. Total unique routes planned: {len(final_routes)} in {total_time:.1f}s")
        return final_routes

    def _create_spatial_grid(self, locations: List[Dict], grid_size: int) -> Dict[Tuple[int, int], List[Dict]]:
        """
        Partitions locations into a grid for efficient spatial queries.
        Returns a dictionary where keys are (grid_x, grid_y) tuples and values are lists of locations.
        """
        grid = {}
        for loc in locations:
            grid_x = int(loc['x_coordinate'] // grid_size)
            grid_y = int(loc['y_coordinate'] // grid_size)
            if (grid_x, grid_y) not in grid:
                grid[(grid_x, grid_y)] = []
            grid[(grid_x, grid_y)].append(loc)
        return grid

    def _get_nearby_cells(self, grid_x: int, grid_y: int, radius: int = 1) -> List[Tuple[int, int]]:
        """
        Gets the coordinates of grid cells within a given radius of a central cell.
        """
        cells = []
        for i in range(-radius, radius + 1):
            for j in range(-radius, radius + 1):
                cells.append((grid_x + i, grid_y + j))
        return cells

    async def _create_mst_optimized(self, locations: List[Dict], location_map: Dict, connected_pairs: set) -> List[Dict]:
        """Creates a Minimum Spanning Tree using Prim's algorithm with a priority queue (heapq)."""
        if not locations:
            return []
        
        import heapq
        import time

        routes = []
        start_node_id = locations[0]['id']
        nodes_to_visit = [(0, start_node_id, start_node_id)]
        visited = set()
        nodes_processed = 0
        max_iterations = len(locations) * 10  # Safety limit to prevent infinite loops
        iterations = 0
        start_time = time.time()
        timeout_seconds = 30  # 30 second timeout

        while nodes_to_visit and len(visited) < len(locations) and iterations < max_iterations:
            iterations += 1
            
            # Timeout protection
            if time.time() - start_time > timeout_seconds:
                print(f"⚠️ MST creation timed out after {timeout_seconds}s, using partial tree")
                break
                
            distance, current_node_id, from_node_id = heapq.heappop(nodes_to_visit)

            if current_node_id in visited:
                continue
            
            visited.add(current_node_id)
            nodes_processed += 1

            # Add a route if it's not the starting node
            if current_node_id != from_node_id:
                from_loc = location_map[from_node_id]
                to_loc = location_map[current_node_id]
                
                pair = tuple(sorted((from_node_id, current_node_id)))
                if pair not in connected_pairs:
                    routes.append({
                        'from': from_loc,
                        'to': to_loc,
                        'importance': 'critical',
                        'distance': distance
                    })
                    connected_pairs.add(pair)

            # Only check unvisited locations to avoid O(n²) complexity
            current_loc = location_map[current_node_id]
            unvisited_locs = [loc for loc in locations if loc['id'] not in visited]
            
            # Limit neighbor checks for very large galaxies
            if len(unvisited_locs) > 50:
                # For large galaxies, only check nearest neighbors
                unvisited_locs.sort(key=lambda loc: self._calculate_distance(current_loc, loc))
                unvisited_locs = unvisited_locs[:20]  # Only check 20 nearest
            
            for other_loc in unvisited_locs:
                dist = self._calculate_distance(current_loc, other_loc)
                heapq.heappush(nodes_to_visit, (dist, other_loc['id'], current_node_id))
            
            # Yield control more frequently for large galaxies
            if nodes_processed % 3 == 0 or len(locations) > 100:
                await asyncio.sleep(0)
        
        if iterations >= max_iterations:
            print(f"⚠️ MST hit iteration limit ({max_iterations}), using partial tree")
        
        return routes

    async def _create_hub_connections_optimized(self, locations: List[Dict], location_map: Dict, spatial_grid: Dict, grid_size: int, connected_pairs: set) -> List[Dict]:
        """
        Creates hub connections from space stations to nearby wealthy colonies using the spatial grid.
        """
        routes = []
        stations = [loc for loc in locations if loc['type'] == 'space_station']
        wealthy_colonies = [loc for loc in locations if loc['type'] == 'colony' and loc['wealth_level'] >= 6]

        if not stations or not wealthy_colonies:
            return []

        for station in stations:
            # Connect to 2-4 nearby wealthy colonies.
            nearby_colonies = []
            grid_x = int(station['x_coordinate'] // grid_size)
            grid_y = int(station['y_coordinate'] // grid_size)
            
            # Search in an expanding radius of grid cells.
            for radius in range(3): # Search up to 2 cells away
                cells_to_check = self._get_nearby_cells(grid_x, grid_y, radius)
                for cell_coord in cells_to_check:
                    if cell_coord in spatial_grid:
                        for loc in spatial_grid[cell_coord]:
                            if loc['type'] == 'colony' and loc['wealth_level'] >= 6:
                                nearby_colonies.append(loc)
                if len(nearby_colonies) >= 5: # Found enough candidates
                    break
            
            # Sort by distance and pick the closest ones.
            nearby_colonies.sort(key=lambda c: self._calculate_distance(station, c))
            
            connections_made = 0
            for colony in nearby_colonies:
                if connections_made >= random.randint(2, 4):
                    break
                
                pair = tuple(sorted((station['id'], colony['id'])))
                if pair not in connected_pairs:
                    routes.append({
                        'from': station,
                        'to': colony,
                        'importance': 'high',
                        'distance': self._calculate_distance(station, colony)
                    })
                    connected_pairs.add(pair)
                    connections_made += 1
        return routes
        
    async def _add_redundant_connections_optimized(self, locations: List[Dict], location_map: Dict, spatial_grid: Dict, grid_size: int, connected_pairs: set) -> List[Dict]:
        """
        Adds redundant connections to locations with low connectivity using the spatial grid.
        """
        routes = []
        
        # First, build a connectivity map.
        connectivity_map = {loc['id']: 0 for loc in locations}
        for pair in connected_pairs:
            connectivity_map[pair[0]] += 1
            connectivity_map[pair[1]] += 1
            
        # Identify locations with 1 or 2 connections.
        low_connectivity_locs = [loc for loc in locations if connectivity_map[loc['id']] <= 2]
        
        print(f"    Adding redundant connections for {len(low_connectivity_locs)} low-connectivity locations...")
        
        processed = 0
        for loc in low_connectivity_locs:
            # Yield control every 10 locations
            if processed % 10 == 0:
                await asyncio.sleep(0.01)
            
            # Find 1-2 nearby locations to connect to.
            nearby_candidates = []
            grid_x = int(loc['x_coordinate'] // grid_size)
            grid_y = int(loc['y_coordinate'] // grid_size)

            # Search nearby grid cells with expanding radius if needed
            max_candidates = 20  # Limit candidates to prevent hanging
            for radius in range(1, 4):  # Try expanding radius if not enough candidates
                if len(nearby_candidates) >= max_candidates:
                    break
                    
                cells_to_check = self._get_nearby_cells(grid_x, grid_y, radius=radius)
                for cell_coord in cells_to_check:
                    if cell_coord in spatial_grid:
                        for candidate in spatial_grid[cell_coord]:
                            if candidate['id'] != loc['id']:
                                # Quick distance check before adding to candidates
                                distance = self._calculate_distance(loc, candidate)
                                if distance < 100:  # Pre-filter by distance
                                    nearby_candidates.append(candidate)
                                    if len(nearby_candidates) >= max_candidates:
                                        break
                        if len(nearby_candidates) >= max_candidates:
                            break
                
                # If we found some candidates, don't expand radius unnecessarily
                if len(nearby_candidates) >= 5:
                    break
            
            # Sort by distance (but limit to reasonable number)
            nearby_candidates = nearby_candidates[:max_candidates]
            nearby_candidates.sort(key=lambda c: self._calculate_distance(loc, c))
            
            connections_to_add = max(0, min(2, 2 - connectivity_map[loc['id']]))  # Ensure non-negative
            connections_made = 0
            
            for target in nearby_candidates:
                if connections_made >= connections_to_add:
                    break
                
                pair = tuple(sorted((loc['id'], target['id'])))
                if pair not in connected_pairs:
                    distance = self._calculate_distance(loc, target)
                    if distance < 100: # Avoid overly long redundant links
                        routes.append({
                            'from': loc,
                            'to': target,
                            'importance': 'low',
                            'distance': distance
                        })
                        connected_pairs.add(pair)
                        # Update connectivity map for future iterations in this loop
                        connectivity_map[loc['id']] += 1
                        connectivity_map[target['id']] += 1
                        connections_made += 1
            
            processed += 1
            
            # Progress reporting for large galaxies
            if len(low_connectivity_locs) > 50 and processed % 25 == 0:
                progress = (processed / len(low_connectivity_locs)) * 100
                print(f"      Redundant connections progress: {progress:.0f}% ({processed}/{len(low_connectivity_locs)})")
        
        print(f"    Added {len(routes)} redundant connections")
        return routes

    async def _create_regional_bridges_optimized(self, locations: List[Dict], location_map: Dict, spatial_grid: Dict, connected_pairs: set) -> List[Dict]:
        """
        Creates long-range "bridge" connections between distant but important locations.
        """
        routes = []
        # Identify important locations (stations or very wealthy colonies) as potential anchors.
        anchors = [loc for loc in locations if loc['type'] == 'space_station' or loc['wealth_level'] >= 8]
        if len(anchors) < 4: # Not enough anchors to create meaningful bridges
            return []

        # For each anchor, find a distant anchor to connect to.
        for anchor in anchors:
            # Sort other anchors by distance, from farthest to closest.
            distant_anchors = sorted(anchors, key=lambda a: self._calculate_distance(anchor, a), reverse=True)
            
            # Try to connect to the farthest one that isn't already connected.
            for target_anchor in distant_anchors:
                if anchor['id'] == target_anchor['id']:
                    continue
                
                pair = tuple(sorted((anchor['id'], target_anchor['id'])))
                if pair not in connected_pairs:
                    routes.append({
                        'from': anchor,
                        'to': target_anchor,
                        'importance': 'medium',
                        'distance': self._calculate_distance(anchor, target_anchor)
                    })
                    connected_pairs.add(pair)
                    break # Move to the next anchor
        return routes

    async def _validate_and_fix_connectivity_optimized(self, all_locations: List[Dict], routes: List[Dict], location_map: Dict) -> List[Dict]:
        """
        Validates overall connectivity and adds connections to fix any isolated clusters.
        """
        if not all_locations:
            return []
            
        # Build adjacency list from the routes planned so far.
        graph = {loc['id']: set() for loc in all_locations}
        for route in routes:
            from_id, to_id = route['from']['id'], route['to']['id']
            graph[from_id].add(to_id)
            graph[to_id].add(from_id)
        
        # Find all connected components (clusters of locations) using Breadth-First Search.
        visited = set()
        components = []
        for loc in all_locations:
            if loc['id'] not in visited:
                component = set()
                q = [loc['id']]
                visited.add(loc['id'])
                component.add(loc['id'])
                
                head = 0
                while head < len(q):
                    current_id = q[head]
                    head += 1
                    for neighbor_id in graph[current_id]:
                        if neighbor_id not in visited:
                            visited.add(neighbor_id)
                            component.add(neighbor_id)
                            q.append(neighbor_id)
                components.append(list(component))
        
        # If there's more than one component, the galaxy is fragmented. We must connect them.
        if len(components) > 1:
            print(f"🔧 Found {len(components)} disconnected components, fixing connectivity...")
            
            # Sort components by size to connect smaller ones to the largest one.
            components.sort(key=len, reverse=True)
            main_component = components[0]
            
            for i in range(1, len(components)):
                isolated_component = components[i]
                
                # Find the closest pair of locations between the main component and the isolated one.
                best_connection = None
                min_dist = float('inf')
                
                # To avoid n*m checks, we check a sample from each component.
                sample_main = random.sample(main_component, min(len(main_component), 30))
                sample_isolated = random.sample(isolated_component, min(len(isolated_component), 30))

                for main_loc_id in sample_main:
                    for iso_loc_id in sample_isolated:
                        dist = self._calculate_distance(location_map[main_loc_id], location_map[iso_loc_id])
                        if dist < min_dist:
                            min_dist = dist
                            best_connection = (location_map[main_loc_id], location_map[iso_loc_id])
                
                if best_connection:
                    from_loc, to_loc = best_connection
                    print(f"🌉 Added emergency bridge connection: {from_loc['name']} ↔ {to_loc['name']}")
                    routes.append({
                        'from': from_loc,
                        'to': to_loc,
                        'importance': 'critical',
                        'distance': min_dist
                    })
                    # Add these new connections to the graph to merge the components for the next iteration.
                    graph[from_loc['id']].add(to_loc['id'])
                    graph[to_loc['id']].add(from_loc['id'])
                    # Conceptually merge the components for the next loop
                    main_component.extend(isolated_component)

        return routes
        
    async def _generate_homes_for_locations(self, locations: List[Dict]) -> int:
        """Generate homes for colonies and space stations"""
        total_homes = 0
        
        for location in locations:
            if location.get('is_derelict', False):
                continue  # No homes in derelict locations
                
            homes_to_generate = 0
            home_type = None
            
            if location['type'] == 'colony':
                # 15% chance for colonies
                if random.random() < 0.45:
                    homes_to_generate = random.randint(1, 5)
                    home_type = "Colonist Dwelling"
            elif location['type'] == 'space_station':
                # 5% chance for space stations
                if random.random() < 0.35:
                    homes_to_generate = random.randint(1, 3)
                    home_type = "Residential Unit"
            
            if homes_to_generate > 0:
                for i in range(homes_to_generate):
                    # Generate unique home number
                    home_number = random.randint(100, 999)
                    home_name = f"{home_type} {home_number}"
                    
                    # Calculate price based on wealth
                    base_price = 15000 if location['type'] == 'colony' else 9000
                    wealth_multiplier = max(0.5, location['wealth_level'] / 5)
                    price = int(base_price * wealth_multiplier)
                    
                    # Generate interior description
                    if location['type'] == 'colony':
                        interior_descriptions = [
                            "A cozy dwelling with synthetic wood floors and a view of the colony plaza.",
                            "A modest home featuring efficient space utilization and modern amenities.",
                            "A comfortable residence with climate-controlled rooms and a small garden area.",
                            "A well-maintained dwelling with panoramic windows overlooking the colony.",
                            "A compact but elegant home with customizable lighting and temperature controls."
                        ]
                    else:  # space station
                        interior_descriptions = [
                            "A sleek residential unit with anti-gravity fixtures and stellar views.",
                            "A modern living space featuring advanced life support and entertainment systems.",
                            "A comfortable unit with adjustable artificial gravity and mood lighting.",
                            "An efficient residential module with space-saving design and holographic windows.",
                            "A premium unit offering panoramic viewports and state-of-the-art amenities."
                        ]
                    
                    interior_desc = random.choice(interior_descriptions)
                    
                    # Generate random activities (2-4 per home)
                    from utils.home_activities import HomeActivityManager
                    activity_manager = HomeActivityManager(self.bot)
                    num_activities = random.randint(2, 4)
                    activities = activity_manager.generate_random_activities(num_activities)
                    
                    # Calculate value modifier based on activities
                    value_modifier = 1.0 + (len(activities) * 0.05)
                    
                    # Insert home into database
                    self.db.execute_query(
                        '''INSERT INTO location_homes 
                           (location_id, home_type, home_name, price, interior_description, 
                            activities, value_modifier, is_available)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, true)''',
                        (location['id'], home_type, home_name, price, interior_desc,
                         ','.join(activities), value_modifier)
                    )

                    # Get the home_id of the just-inserted home
                    home_id = self.db.execute_query(
                        '''SELECT home_id FROM location_homes 
                           WHERE location_id = %s AND home_name = %s 
                           ORDER BY home_id DESC LIMIT 1''',
                        (location['id'], home_name),
                        fetch='one'
                    )[0]
                    
                    # Insert activities
                    for activity_type in activities:
                        activity_data = activity_manager.activity_types.get(activity_type, {})
                        self.db.execute_query(
                            '''INSERT INTO home_activities 
                               (home_id, activity_type, activity_name)
                               VALUES (%s, %s, %s)''',
                            (home_id, activity_type, activity_data.get('name', activity_type))
                        )
                    
                    total_homes += 1
        
        return total_homes
        
    async def _simulate_gate_movements_for_affected(self, affected_gate_ids: list, intensity: int) -> Dict:
        """Simulate gate status changes for gates that had corridors deactivated"""
        
        results = {
            'gates_moved': 0,
            'gates_abandoned': 0,
            'affected_gates': []
        }
        
        if not affected_gate_ids:
            return results
        
        # Get details for affected gates
        gate_placeholders = ','.join('%s' * len(affected_gate_ids))
        affected_gates = self.db.execute_query(
            f"SELECT location_id, name FROM locations WHERE location_id IN ({gate_placeholders}) AND location_type = 'gate' AND gate_status = 'active'",
            affected_gate_ids,
            fetch='all'
        )
        
        for gate in affected_gates:
            gate_id, gate_name = gate
            
            # Check how many active corridors this gate still has after the shift
            remaining_corridors = self.db.execute_query(
                """SELECT COUNT(*) FROM corridors 
                   WHERE (origin_location = %s OR destination_location = %s) 
                   AND is_active = true
                   AND name NOT LIKE '%Approach%' 
                   AND name NOT LIKE '%Arrival%' 
                   AND name NOT LIKE '%Departure%'""",
                (gate_id, gate_id),
                fetch='one'
            )[0]
            
            # Gates with no remaining main corridors are disconnected
            if remaining_corridors == 0:
                # Gate becomes either moving or abandoned
                if random.random() < 0.6:  # 60% chance to become moving
                    hours_until_reconnection = random.randint(4, 24)
                    reconnection_time = datetime.now() + timedelta(hours=hours_until_reconnection)
                    
                    self.db.execute_query(
                        "UPDATE locations SET gate_status = 'moving', reconnection_eta = %s WHERE location_id = %s",
                        (reconnection_time, gate_id)
                    )
                    
                    # Ensure moving gate has local space connections
                    await self._ensure_moving_gate_local_connections(gate_id, gate_name)
                    
                    results['gates_abandoned'] += 1
                    results['affected_gates'].append(f"🔄 {gate_name} is moving - reconnecting in {hours_until_reconnection} hours")
                    print(f"🔄 Gate {gate_name} lost connections, now moving - will reconnect in {hours_until_reconnection} hours")
                    
                else:  # 40% chance to become unused/abandoned
                    current_time = datetime.now()
                    self.db.execute_query(
                        """UPDATE locations SET 
                           gate_status = 'unused', 
                           abandoned_since = %s,
                           has_shops = false, 
                           has_medical = false,
                           has_repairs = false,
                           has_fuel = false,
                           population = 0
                           WHERE location_id = %s""",
                        (current_time, gate_id)
                    )
                    
                    # Remove static NPCs from abandoned gates
                    self.db.execute_query(
                        "DELETE FROM static_npcs WHERE location_id = %s",
                        (gate_id,)
                    )
                    
                    results['gates_abandoned'] += 1
                    results['affected_gates'].append(f"⚫ {gate_name} became unused due to lost connections")
                    print(f"⚫ Gate {gate_name} lost all connections and became abandoned")
                    
            elif remaining_corridors <= 2:  # Gates with few connections might become unstable
                # Small chance (based on intensity) that low-connectivity gates also become affected
                instability_chance = intensity * 0.05  # 5% per intensity level
                if random.random() < instability_chance:
                    hours_until_reconnection = random.randint(2, 8)  # Shorter time for partially connected gates
                    reconnection_time = datetime.now() + timedelta(hours=hours_until_reconnection)
                    
                    self.db.execute_query(
                        "UPDATE locations SET gate_status = 'moving', reconnection_eta = %s WHERE location_id = %s",
                        (reconnection_time, gate_id)
                    )
                    
                    # Ensure moving gate has local space connections
                    await self._ensure_moving_gate_local_connections(gate_id, gate_name)
                    
                    results['gates_abandoned'] += 1
                    results['affected_gates'].append(f"🔄 {gate_name} destabilized - reconnecting in {hours_until_reconnection} hours")
                    print(f"🔄 Gate {gate_name} destabilized by corridor shifts - will reconnect in {hours_until_reconnection} hours")
        
        return results


    async def _check_and_reconnect_moving_gates(self):
        """Check for moving gates that have reached their reconnection time"""
        
        # Find gates that are ready to reconnect
        moving_gates = self.db.execute_query(
            """SELECT location_id, name, x_coordinate, y_coordinate, reconnection_eta 
               FROM locations 
               WHERE location_type = 'gate' 
               AND gate_status = 'moving' 
               AND reconnection_eta IS NOT NULL 
               AND reconnection_eta <= NOW()""",
            fetch='all'
        )
        
        if not moving_gates:
            return
        
        for gate in moving_gates:
            gate_id, gate_name, gate_x, gate_y, eta = gate
            
            print(f"🔄 Reconnecting gate: {gate_name}")
            
            # Update gate status back to active and restore services with correct gate defaults
            gate_population = random.randint(15, 40)  # Gates have small operational crews
            self.db.execute_query(
                """UPDATE locations SET 
                   gate_status = 'active', 
                   reconnection_eta = NULL,
                   population = %s,
                   has_shops = true,
                   has_medical = true,
                   has_repairs = true,
                   has_fuel = true,
                   has_upgrades = false
                   WHERE location_id = %s""",
                (gate_population, gate_id)
            )
            
            # Use existing NPC system to restore NPCs
            npc_cog = self.bot.get_cog('NPCCog')
            if npc_cog:
                await npc_cog.create_static_npcs_for_location(gate_id, gate_population, 'gate')
            
            # Find nearby gates to connect to (within reasonable distance)
            nearby_gates = self.db.execute_query(
                """SELECT location_id, name, x_coordinate, y_coordinate 
                   FROM locations 
                   WHERE location_type = 'gate' 
                   AND gate_status = 'active' 
                   AND location_id != %s
                   ORDER BY ((x_coordinate - %s) * (x_coordinate - %s) + (y_coordinate - %s) * (y_coordinate - %s))
                   LIMIT 3""",
                (gate_id, gate_x, gate_x, gate_y, gate_y),
                fetch='all'
            )
            
            # Create new corridors to nearby gates
            for target_gate in nearby_gates:
                target_id, target_name, target_x, target_y = target_gate
                
                # Check if corridor already exists
                existing = self.db.execute_query(
                    """SELECT corridor_id FROM corridors 
                       WHERE (origin_location = %s AND destination_location = %s)
                       OR (origin_location = %s AND destination_location = %s)""",
                    (gate_id, target_id, target_id, gate_id),
                    fetch='one'
                )
                
                if not existing:
                    # Calculate distance for travel time using gated route calculations
                    distance = math.sqrt((target_x - gate_x)**2 + (target_y - gate_y)**2)
                    approach_time, main_time = self._calculate_gated_route_times(distance)
                    fuel_cost = max(20, int(distance * 0.8))
                    danger_level = random.randint(2, 4)  # Gated corridor danger
                    
                    # Create proper gated corridor (gate to gate should be gated, not local space)
                    corridor_name = f"{gate_name} - {target_name} Route"
                    
                    # Create bidirectional gated corridors
                    self.db.execute_query(
                        """INSERT INTO corridors (name, origin_location, destination_location, 
                           travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE)""",
                        (corridor_name, gate_id, target_id, main_time, fuel_cost, danger_level, 'gated')
                    )
                    
                    self.db.execute_query(
                        """INSERT INTO corridors (name, origin_location, destination_location, 
                           travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE)""",
                        (f"{target_name} - {gate_name} Route", target_id, gate_id, main_time, fuel_cost, danger_level, 'gated')
                    )
                    
                    print(f"  ✅ Connected {gate_name} ↔ {target_name} (gated corridors)")
            
            # Reactivate any deactivated corridors from when it became moving
            self.db.execute_query(
                """UPDATE corridors 
                   SET is_active = true 
                   WHERE (origin_location = %s OR destination_location = %s)
                   AND is_active = false""",
                (gate_id, gate_id)
            )
            
            print(f"✅ Gate {gate_name} successfully reconnected to the network")
    
    async def _check_for_gates_to_reactivate(self):
        """Check for long-abandoned gates that can potentially start moving again"""
        
        # Find gates that have been abandoned for at least 3 days
        cutoff_time = datetime.now() - timedelta(days=3)
        
        long_abandoned_gates = self.db.execute_query(
            """SELECT location_id, name, abandoned_since 
               FROM locations 
               WHERE location_type = 'gate' 
               AND gate_status = 'unused' 
               AND abandoned_since IS NOT NULL 
               AND abandoned_since <= %s""",
            (cutoff_time,),
            fetch='all'
        )
        
        if not long_abandoned_gates:
            return
        
        for gate in long_abandoned_gates:
            gate_id, gate_name, abandoned_since = gate
            
            # 10% chance per check (every 30 minutes) that an abandoned gate starts moving
            # This roughly translates to about 48% chance per day for gates abandoned 3+ days
            if random.random() < 0.1:
                print(f"🔄 Abandoned gate {gate_name} is beginning to move after long abandonment")
                
                # Calculate reconnection time (6-48 hours from now)
                hours_until_reconnection = random.randint(6, 48)
                reconnection_time = datetime.now() + timedelta(hours=hours_until_reconnection)
                
                # Start restoring some basic services as the gate prepares to move
                basic_population = random.randint(5, 15)  # Skeleton crew for gates
                
                self.db.execute_query(
                    """UPDATE locations SET 
                       gate_status = 'moving',
                       reconnection_eta = %s,
                       abandoned_since = NULL,
                       population = %s,
                       has_fuel = true,
                       has_repairs = true
                       WHERE location_id = %s""",
                    (reconnection_time, basic_population, gate_id)
                )
                
                # Ensure moving gate has local space connections
                await self._ensure_moving_gate_local_connections(gate_id, gate_name)
                
                print(f"  Gate will reconnect in {hours_until_reconnection} hours with basic services")
    
    
    async def _gate_check_loop(self):
        """Background task to check for moving gates more frequently"""
        try:
            await self.bot.wait_until_ready()
            
            # Initial delay before first check (30 minutes)
            await asyncio.sleep(1800)
            
            while not self.bot.is_closed():
                try:
                    # Check if galaxy exists
                    location_count = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.db.execute_query,
                            "SELECT COUNT(*) FROM locations",
                            fetch='one'
                        ),
                        timeout=10.0
                    )
                    location_count = location_count[0] if location_count else 0
                    
                    if location_count > 0:
                        # Check for moving gates that need reconnection
                        await self._check_and_reconnect_moving_gates()
                        
                        # Check for long-abandoned gates that can start moving
                        await self._check_for_gates_to_reactivate()
                    
                    # Wait 30 minutes before next check
                    await asyncio.sleep(1800)
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"⚠️ Error in gate check loop: {e}")
                    await asyncio.sleep(1800)  # Wait 30 minutes on error
                    
        except asyncio.CancelledError:
            print("🔄 Gate check task cancelled")
        except Exception as e:
            print(f"❌ Fatal error in gate check loop: {e}")
    def _create_minimum_spanning_tree(self, locations: List[Dict]) -> List[Dict]:
        """Create minimum spanning tree to ensure all locations are connected"""
        if not locations:
            return []
        
        routes = []
        connected = {locations[0]['id']}  # Start with first location
        unconnected = {loc['id']: loc for loc in locations[1:]}
        
        while unconnected:
            best_distance = float('inf')
            best_connection = None
            
            # Find shortest connection from connected to unconnected
            for connected_id in connected:
                connected_loc = next(loc for loc in locations if loc['id'] == connected_id)
                
                for unconnected_id, unconnected_loc in unconnected.items():
                    distance = self._calculate_distance(connected_loc, unconnected_loc)
                    if distance < best_distance:
                        best_distance = distance
                        best_connection = (connected_loc, unconnected_loc)
            
            if best_connection:
                from_loc, to_loc = best_connection
                routes.append({
                    'from': from_loc,
                    'to': to_loc,
                    'importance': 'medium',
                    'distance': best_distance
                })
                connected.add(to_loc['id'])
                del unconnected[to_loc['id']]
        
        return routes

    def _create_hub_connections(self, stations: List[Dict], colonies: List[Dict]) -> List[Dict]:
        """Create hub connections between stations and high-value colonies"""
        routes = []
        
        for station in stations:
            # Connect each station to 2-4 nearby high-value colonies
            wealthy_colonies = [c for c in colonies if c['wealth_level'] >= 6]
            nearby_wealthy = self._find_nearby_locations(station, wealthy_colonies, max_distance=70)
            
            connection_count = min(len(nearby_wealthy), random.randint(2, 4))
            for colony in nearby_wealthy[:connection_count]:
                routes.append({
                    'from': station,
                    'to': colony,
                    'importance': 'high',
                    'distance': self._calculate_distance(station, colony)
                })
        
        return routes

    def _create_regional_bridges(self, all_locations: List[Dict], existing_routes: List[Dict]) -> List[Dict]:
        """Create bridge connections between different regions of the galaxy"""
        routes = []
        
        # Analyze spatial distribution to identify regions
        regions = self._identify_spatial_regions(all_locations)
        
        # Create cross-regional connections
        for i, region_a in enumerate(regions):
            for j, region_b in enumerate(regions[i+1:], i+1):
                # Find best connection points between regions
                best_connections = self._find_best_inter_region_connections(region_a, region_b)
                
                # Add 1-2 bridge connections between each pair of regions
                for connection in best_connections[:random.randint(1, 2)]:
                    routes.append({
                        'from': connection[0],
                        'to': connection[1],
                        'importance': 'medium', 
                        'distance': self._calculate_distance(connection[0], connection[1])
                    })
        
        return routes

    def _identify_spatial_regions(self, locations: List[Dict]) -> List[List[Dict]]:
        """Identify spatial regions in the galaxy for better connectivity planning"""
        if len(locations) <= 6:
            return [locations]  # Too few locations to regionalize
        
        # Simple clustering based on position
        regions = []
        used_locations = set()
        
        # Create regions of roughly 8-15 locations each
        target_region_size = max(6, len(locations) // 4)
        
        while len(used_locations) < len(locations):
            # Find an unused location as region center
            available = [loc for loc in locations if loc['id'] not in used_locations]
            if not available:
                break
                
            # Pick a central location (prefer stations/wealthy colonies)
            region_center = max(available, key=lambda loc: (
                loc['type'] == 'space_station',
                loc['wealth_level'],
                -len([l for l in available if self._calculate_distance(loc, l) < 30])
            ))
            
            # Build region around this center
            region = [region_center]
            used_locations.add(region_center['id'])
            
            # Add nearby locations to this region
            candidates = [loc for loc in available if loc['id'] != region_center['id']]
            candidates.sort(key=lambda loc: self._calculate_distance(region_center, loc))
            
            for candidate in candidates:
                if len(region) >= target_region_size:
                    break
                if candidate['id'] not in used_locations:
                    # Add if close enough to region center or any region member
                    min_distance_to_region = min(
                        self._calculate_distance(candidate, member) 
                        for member in region
                    )
                    if min_distance_to_region <= 40:
                        region.append(candidate)
                        used_locations.add(candidate['id'])
            
            regions.append(region)
        
        return regions

    def _find_best_inter_region_connections(self, region_a: List[Dict], region_b: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """Find the best connection points between two regions"""
        connections = []
        
        for loc_a in region_a:
            for loc_b in region_b:
                distance = self._calculate_distance(loc_a, loc_b)
                # Prefer stations and wealthy colonies as connection points
                priority = (
                    (loc_a['type'] == 'space_station') + (loc_b['type'] == 'space_station'),
                    (loc_a['wealth_level'] + loc_b['wealth_level']),
                    -distance  # Closer is better
                )
                connections.append(((loc_a, loc_b), distance, priority))
        
        # Sort by priority (stations first, then wealth, then distance)
        connections.sort(key=lambda x: x[2], reverse=True)
        
        return [conn[0] for conn in connections[:3]]  # Return top 3 candidates

    def _add_redundant_connections(self, all_locations: List[Dict], existing_routes: List[Dict]) -> List[Dict]:
        """Add redundant connections to prevent fragmentation"""
        routes = []
        
        # Calculate current connectivity for each location
        connectivity_map = {}
        for loc in all_locations:
            connectivity_map[loc['id']] = sum(1 for route in existing_routes 
                                            if route['from']['id'] == loc['id'] or route['to']['id'] == loc['id'])
        
        # Identify locations with low connectivity
        low_connectivity = [loc for loc in all_locations if connectivity_map[loc['id']] <= 2]
        
        for location in low_connectivity:
            # Find 1-2 additional connections for low-connectivity locations
            potential_targets = [loc for loc in all_locations if loc['id'] != location['id']]
            
            # Exclude already connected locations
            connected_ids = set()
            for route in existing_routes:
                if route['from']['id'] == location['id']:
                    connected_ids.add(route['to']['id'])
                elif route['to']['id'] == location['id']:
                    connected_ids.add(route['from']['id'])
            
            potential_targets = [loc for loc in potential_targets if loc['id'] not in connected_ids]
            
            if potential_targets:
                # Sort by distance and select 1-2 closest
                potential_targets.sort(key=lambda loc: self._calculate_distance(location, loc))
                
                for target in potential_targets[:random.randint(1, 2)]:
                    distance = self._calculate_distance(location, target)
                    if distance <= 80:  # Don't create extremely long connections
                        routes.append({
                            'from': location,
                            'to': target,
                            'importance': 'low',
                            'distance': distance
                        })
        
        return routes

    def _validate_and_fix_connectivity(self, all_locations: List[Dict], routes: List[Dict]) -> List[Dict]:
        """Validate overall connectivity and fix issues"""
        
        # Build adjacency list
        graph = {loc['id']: set() for loc in all_locations}
        for route in routes:
            from_id, to_id = route['from']['id'], route['to']['id']
            graph[from_id].add(to_id)
            graph[to_id].add(from_id)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        # If we have multiple components, connect them
        if len(components) > 1:
            print(f"🔧 Found {len(components)} disconnected components, fixing connectivity...")
            
            # Connect each component to the largest one
            largest_component = max(components, key=len)
            
            for component in components:
                if component == largest_component:
                    continue
                
                # Find best connection between this component and the largest
                best_connection = None
                best_distance = float('inf')
                
                for loc_id_a in component:
                    loc_a = next(loc for loc in all_locations if loc['id'] == loc_id_a)
                    for loc_id_b in largest_component:
                        loc_b = next(loc for loc in all_locations if loc['id'] == loc_id_b)
                        distance = self._calculate_distance(loc_a, loc_b)
                        
                        if distance < best_distance:
                            best_distance = distance
                            best_connection = (loc_a, loc_b)
                
                if best_connection:
                    routes.append({
                        'from': best_connection[0],
                        'to': best_connection[1],
                        'importance': 'medium',
                        'distance': best_distance
                    })
                    print(f"🌉 Added bridge connection: {best_connection[0]['name']} ↔ {best_connection[1]['name']}")
        
        return routes

    async def _create_dormant_corridors(self, conn, all_locations: List[Dict], active_routes: List[Dict]):
        """Creates dormant corridors with radical optimization using spatial binning and micro-transactions"""
        
        # Commit current transaction before starting dormant generation (only if conn exists)
        if conn is not None:
            self.db.commit_transaction(conn)
            conn = None  # Clear the connection reference
        
        active_pairs = {tuple(sorted([r['from']['id'], r['to']['id']])) for r in active_routes}
        num_locs = len(all_locations)
        
        # Calculate target dormant corridors with reduced density for better gameplay
        # Scale based on galaxy size to prevent exponential growth
        if num_locs <= 50:
            multiplier = 1.5  # Small galaxies can handle more density
        elif num_locs <= 150:
            multiplier = 1.3  # Medium galaxies need moderation
        else:
            multiplier = 1.2  # Large galaxies must be sparse
        
        target_dormant_total = int(num_locs * multiplier)
        
        # Cap total dormant corridors to prevent overcrowding
        max_dormant_cap = min(500, num_locs * 5)  # Never exceed 5x locations or 500 total
        target_dormant_total = min(target_dormant_total, max_dormant_cap)
        
        print(f"🌫️ Generating {target_dormant_total} dormant corridors for {num_locs} locations using spatial optimization...")
        
        # Create spatial bins for ultra-fast proximity lookups
        spatial_bins = self._create_spatial_bins(all_locations, bin_size=25)
        
        corridors_created = 0
        max_attempts = target_dormant_total * 3  # Prevent infinite loops
        attempts = 0
        
        # Process in very small independent transactions
        batch_size = 25  # Much smaller batches
        current_batch = []
        
        while corridors_created < target_dormant_total and attempts < max_attempts:
            attempts += 1
            
            # Pick a random location
            loc_a = random.choice(all_locations)
            
            # Get nearby locations using spatial binning (much faster than distance calc)
            nearby_candidates = self._get_nearby_from_bins(loc_a, spatial_bins, max_candidates=8)
            
            if not nearby_candidates:
                continue
                
            # Pick a random nearby candidate
            loc_b = random.choice(nearby_candidates)
            
            pair = tuple(sorted([loc_a['id'], loc_b['id']]))
            
            # Validate location IDs to prevent foreign key constraint violations
            if loc_a['id'] <= 0 or loc_b['id'] <= 0:
                continue
            
            # Skip if already exists
            if pair in active_pairs:
                continue
                
            # Quick distance check (only now do we calculate distance)
            distance = self._calculate_distance(loc_a, loc_b)
            if distance > 60:  # Skip very long corridors
                continue
                
            # Create corridor data
            name = self._generate_corridor_name(loc_a, loc_b)
            fuel = max(10, int(distance * 0.8) + 5)
            danger = random.randint(2, 5)
            travel_time = self._calculate_ungated_route_time(distance)
            
            # Determine corridor types for both directions
            corridor_type_ab = self._determine_corridor_type(loc_a['id'], loc_b['id'], f"{name} (Dormant)")
            corridor_type_ba = self._determine_corridor_type(loc_b['id'], loc_a['id'], f"{name} Return (Dormant)")
            
            # Add to batch (bidirectional)
            current_batch.extend([
                (f"{name} (Dormant)", loc_a['id'], loc_b['id'], travel_time, fuel, danger, corridor_type_ab),
                (f"{name} Return (Dormant)", loc_b['id'], loc_a['id'], travel_time, fuel, danger, corridor_type_ba)
            ])
            
            active_pairs.add(pair)
            corridors_created += 2
            
            # Insert batch in micro-transaction when ready
            if len(current_batch) >= batch_size:
                await self._insert_dormant_batch(current_batch)
                current_batch = []
                
                # Progress and yield much more frequently
                if corridors_created % 100 == 0:
                    progress = (corridors_created / target_dormant_total) * 100
                    print(f"    🌫️ Dormant corridors: {progress:.0f}% ({corridors_created}/{target_dormant_total})")
                    
                # Yield control very frequently
                await asyncio.sleep(0.05)
        
        # Insert remaining batch
        if current_batch:
            await self._insert_dormant_batch(current_batch)
        
        print(f"🌫️ Created {corridors_created} dormant corridor segments in {attempts} attempts")

    def _create_spatial_bins(self, locations: List[Dict], bin_size: float = 25) -> Dict:
        """Create spatial bins for ultra-fast proximity lookups"""
        bins = {}
        
        for loc in locations:
            bin_x = int(loc['x_coordinate'] // bin_size)
            bin_y = int(loc['y_coordinate'] // bin_size)
            bin_key = (bin_x, bin_y)
            
            if bin_key not in bins:
                bins[bin_key] = []
            bins[bin_key].append(loc)
        
        return bins

    def _get_nearby_from_bins(self, location: Dict, spatial_bins: Dict, max_candidates: int = 8) -> List[Dict]:
        """Get nearby locations using spatial bins (much faster than distance calculations)"""
        bin_size = 25
        bin_x = int(location['x_coordinate'] // bin_size)
        bin_y = int(location['y_coordinate'] // bin_size)
        
        nearby = []
        
        # Check the location's bin and adjacent bins (3x3 grid)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                check_bin = (bin_x + dx, bin_y + dy)
                if check_bin in spatial_bins:
                    for candidate in spatial_bins[check_bin]:
                        if candidate['id'] != location['id']:
                            nearby.append(candidate)
                            
                            # Early exit when we have enough candidates
                            if len(nearby) >= max_candidates:
                                return nearby[:max_candidates]
        
        return nearby

    async def _insert_dormant_batch(self, batch_data: List[tuple]):
        """Insert dormant corridors in independent micro-transaction"""
        if not batch_data:
            return
            
        # Use completely independent transaction
        micro_conn = self.db.begin_transaction()
        try:
            query = '''INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time, fuel_cost, 
                        danger_level, corridor_type, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, TRUE)'''
            self.db.executemany_in_transaction(micro_conn, query, batch_data)
            self.db.commit_transaction(micro_conn)
        except Exception as e:
            self.db.rollback_transaction(micro_conn)
            print(f"❌ Error inserting dormant batch: {e}")
        finally:
            micro_conn = None
    
    @galaxy_group.command(name="fix_routes", description="Fix missing local space routes and optionally re-shift corridors")
    @app_commands.describe(
        reshift="Run a corridor shift after fixing routes (default: False)",
        shift_intensity="Intensity of corridor shift if reshift is True (1-5)"
    )
    async def fix_routes(self, interaction: discord.Interaction, reshift: bool = False, shift_intensity: int = 2):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Track fixes
            fixes = {
                'missing_approaches': 0,
                'missing_arrivals': 0,
                'missing_departures': 0,
                'total_fixed': 0
            }
            
            # Batch fetch all required data upfront - ONLY ACTIVE GATES
            all_gates = self.db.execute_query(
                """SELECT location_id, name, x_coordinate, y_coordinate 
                   FROM locations 
                   WHERE location_type = 'gate' AND gate_status = 'active'""",
                fetch='all'
            )
            
            all_major_locations = self.db.execute_query(
                """SELECT location_id, name, x_coordinate, y_coordinate, location_type
                   FROM locations
                   WHERE location_type IN ('colony', 'space_station', 'outpost')""",
                fetch='all'
            )
            
            # Get ALL existing local space corridors in one query
            existing_local_corridors = self.db.execute_query(
                """SELECT origin_location, destination_location, name
                   FROM corridors
                   WHERE name LIKE '%Approach%' 
                      OR name LIKE '%Arrival%' 
                      OR name LIKE '%Departure%'""",
                fetch='all'
            )
            
            # Build lookup dictionaries for O(1) access
            existing_corridors_lookup = {}
            for origin, dest, name in existing_local_corridors:
                key = f"{origin}-{dest}"
                if 'Approach' in name:
                    existing_corridors_lookup[f"approach_{key}"] = True
                elif 'Arrival' in name:
                    existing_corridors_lookup[f"arrival_{key}"] = True
                elif 'Departure' in name:
                    existing_corridors_lookup[f"departure_{key}"] = True
            
            # Process each gate
            for gate_id, gate_name, gx, gy in all_gates:
                # Find nearest major location
                nearest_loc = None
                min_distance = float('inf')
                
                for loc_id, loc_name, lx, ly, loc_type in all_major_locations:
                    distance = math.sqrt((gx - lx) ** 2 + (gy - ly) ** 2)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_loc = (loc_id, loc_name, lx, ly)
                
                if not nearest_loc:
                    continue
                    
                loc_id, loc_name, lx, ly = nearest_loc
                
                # Check for missing Approach corridor
                approach_key = f"approach_{loc_id}-{gate_id}"
                if approach_key not in existing_corridors_lookup:
                    approach_time = int(min_distance * 3) + 60
                    fuel_cost = max(5, int(min_distance * 0.2))
                    
                    self.db.execute_query(
                        """INSERT INTO corridors 
                           (name, origin_location, destination_location, travel_time,
                            fuel_cost, danger_level, corridor_type, is_active, is_generated)
                           VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                        (f"{gate_name} Approach", loc_id, gate_id, approach_time, fuel_cost, 'local_space')
                    )
                    fixes['missing_approaches'] += 1
                    print(f"✅ Fixed approach: {loc_name} -> {gate_name}")
                
                # Check for missing Arrival corridor
                arrival_key = f"arrival_{gate_id}-{loc_id}"
                if arrival_key not in existing_corridors_lookup:
                    arrival_time = int(min_distance * 3) + 60
                    fuel_cost = max(5, int(min_distance * 0.2))
                    
                    self.db.execute_query(
                        """INSERT INTO corridors 
                           (name, origin_location, destination_location, travel_time,
                            fuel_cost, danger_level, corridor_type, is_active, is_generated)
                           VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                        (f"{gate_name} Arrival", gate_id, loc_id, arrival_time, fuel_cost, 'local_space')
                    )
                    fixes['missing_arrivals'] += 1
                    print(f"✅ Fixed arrival: {gate_name} -> {loc_name}")
            
            # Check for missing return departures - batch fetch all gated corridors
            gated_corridors = self.db.execute_query(
                """SELECT DISTINCT c.corridor_id, c.name, c.origin_location, c.destination_location,
                          lo.name as origin_name, ld.name as dest_name
                   FROM corridors c
                   JOIN locations lo ON c.origin_location = lo.location_id
                   JOIN locations ld ON c.destination_location = ld.location_id
                   WHERE lo.location_type = 'gate' 
                   AND ld.location_type = 'gate'
                   AND c.name NOT LIKE '%Return%'
                   AND c.name NOT LIKE '%Approach%'
                   AND c.name NOT LIKE '%Arrival%'
                   AND c.name NOT LIKE '%Departure%'
                   AND c.corridor_type != 'ungated'
                   AND c.is_active = true""",
                fetch='all'
            )
            
            # Get all gate-to-location connections in one query
            gate_connections = self.db.execute_query(
                """SELECT c.origin_location as gate_id, c.destination_location as loc_id,
                          l.name as loc_name, l.x_coordinate, l.y_coordinate,
                          g.x_coordinate as gate_x, g.y_coordinate as gate_y
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   JOIN locations g ON c.origin_location = g.location_id
                   WHERE c.name LIKE '%Arrival%'
                   AND l.location_type != 'gate'
                   AND g.location_type = 'gate'""",
                fetch='all'
            )
            
            # Build gate connection lookup
            gate_to_locations = {}
            for gate_id, loc_id, loc_name, lx, ly, gx, gy in gate_connections:
                if gate_id not in gate_to_locations:
                    gate_to_locations[gate_id] = []
                gate_to_locations[gate_id].append((loc_id, loc_name, lx, ly, gx, gy))
            
            # Process return departures
            for corridor_id, base_name, origin_gate, dest_gate, origin_name, dest_name in gated_corridors:
                if dest_gate in gate_to_locations:
                    for loc_id, loc_name, lx, ly, gx, gy in gate_to_locations[dest_gate]:
                        departure_name = f"{base_name} Return Departure"
                        
                        # Check if this specific departure exists
                        exists = any(
                            origin == loc_id and dest == dest_gate and departure_name in name
                            for origin, dest, name in existing_local_corridors
                        )
                        
                        if not exists:
                            distance = math.sqrt((lx - gx) ** 2 + (ly - gy) ** 2)
                            dep_time = int(distance * 3) + 60
                            fuel_cost = max(5, int(distance * 0.2))
                            
                            self.db.execute_query(
                                """INSERT INTO corridors 
                                   (name, origin_location, destination_location, travel_time,
                                    fuel_cost, danger_level, corridor_type, is_active, is_generated)
                                   VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                                (departure_name, loc_id, dest_gate, dep_time, fuel_cost, 'local_space')
                            )
                            fixes['missing_departures'] += 1
                            print(f"✅ Fixed return departure for {base_name}")
            
            fixes['total_fixed'] = fixes['missing_approaches'] + fixes['missing_arrivals'] + fixes['missing_departures']
            
            # Build response embed
            embed = discord.Embed(
                title="🔧 Route Fixing Complete",
                description=f"Fixed {fixes['total_fixed']} missing local space routes",
                color=0x00ff00
            )
            
            if fixes['total_fixed'] > 0:
                embed.add_field(
                    name="🚀 Routes Restored",
                    value=f"• Approach routes: {fixes['missing_approaches']}\n"
                          f"• Arrival routes: {fixes['missing_arrivals']}\n"
                          f"• Return departures: {fixes['missing_departures']}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ All Good",
                    value="No missing local space routes found!",
                    inline=False
                )
            
            # Run corridor shift if requested
            if reshift:
                if shift_intensity < 1 or shift_intensity > 5:
                    shift_intensity = 2
                
                embed.add_field(
                    name="🌀 Running Corridor Shift",
                    value=f"Executing intensity {shift_intensity} shift...",
                    inline=False
                )
                
                # Execute the shift
                shift_results = await self._execute_corridor_shifts(shift_intensity)
                
                embed.add_field(
                    name="📊 Shift Results",
                    value=f"• Activated: {shift_results['activated']} corridors\n"
                          f"• Deactivated: {shift_results['deactivated']} corridors\n"
                          f"• Destinations changed: {shift_results.get('destinations_changed', 0)} corridors\n"
                          f"• New dormant: {shift_results['new_dormant']} corridors",
                    inline=False
                )
            
            # Check connectivity
            connectivity_status = await self._analyze_connectivity_post_shift()
            embed.add_field(
                name="🌐 Connectivity Status",
                value=connectivity_status,
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in fix_routes: {str(e)}")
            await interaction.followup.send(f"Error fixing routes: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="fix_moving_gates", description="Fix moving gates to have proper local space connections")
    async def fix_moving_gates(self, interaction: discord.Interaction):
        """Fix moving gates that may be missing local space connections"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Find all moving gates
            moving_gates = self.db.execute_query(
                """SELECT location_id, name FROM locations 
                   WHERE location_type = 'gate' AND gate_status = 'moving'""",
                fetch='all'
            )
            
            if not moving_gates:
                await interaction.followup.send("✅ No moving gates found.", ephemeral=True)
                return
            
            fixed_count = 0
            for gate_id, gate_name in moving_gates:
                # Check if gate has any local space connections
                local_connections = self.db.execute_query(
                    """SELECT COUNT(*) FROM corridors 
                       WHERE (origin_location = %s OR destination_location = %s)
                       AND is_active = true
                       AND (name LIKE '%Local Space%' OR name LIKE '%Approach%' OR 
                            name LIKE '%Arrival%' OR name LIKE '%Departure%')""",
                    (gate_id, gate_id),
                    fetch='one'
                )[0]
                
                if local_connections == 0:
                    print(f"🔧 Fixing moving gate with no local connections: {gate_name}")
                    await self._ensure_moving_gate_local_connections(gate_id, gate_name)
                    fixed_count += 1
                else:
                    print(f"✅ Moving gate {gate_name} already has {local_connections} local connections")
            
            embed = discord.Embed(
                title="🔄 Moving Gates Fixed",
                description=f"Fixed {fixed_count} moving gates that were missing local space connections.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="Gates Processed",
                value=f"{len(moving_gates)} moving gates checked",
                inline=True
            )
            
            embed.add_field(
                name="Gates Fixed",
                value=f"{fixed_count} gates needed local space connections",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Error in fix_moving_gates: {str(e)}")
            await interaction.followup.send(f"Error fixing moving gates: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="activate_gate_routes", description="Force activate all routes from current moving gate")
    async def activate_gate_routes(self, interaction: discord.Interaction):
        """Force activate all corridors from current location if it's a moving gate"""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get user's current location
            char_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_location or not char_location[0]:
                await interaction.followup.send("You don't have a current location set.", ephemeral=True)
                return
                
            location_id = char_location[0]
            
            # Check if it's a moving gate
            location_info = self.db.execute_query(
                "SELECT name, location_type, gate_status FROM locations WHERE location_id = %s",
                (location_id,), fetch='one'
            )
            
            if not location_info:
                await interaction.followup.send("Location not found.", ephemeral=True)
                return
                
            loc_name, loc_type, gate_status = location_info
            
            if loc_type != 'gate' or gate_status != 'moving':
                await interaction.followup.send(f"This only works for moving gates. Current: {loc_type} ({gate_status or 'N/A'})", ephemeral=True)
                return
            
            # Activate ALL corridors from this moving gate
            activated_count = self.db.execute_query(
                "UPDATE corridors SET is_active = true WHERE origin_location = %s AND is_active = false",
                (location_id,)
            )
            
            await interaction.followup.send(f"✅ Activated {activated_count} inactive corridors from {loc_name}. Try `/travel routes` now!", ephemeral=True)
            
        except Exception as e:
            print(f"Error in activate_gate_routes: {str(e)}")
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="fix_all_moving_gate_routes", description="Fix route visibility for ALL moving gates galaxy-wide")
    async def fix_all_moving_gate_routes(self, interaction: discord.Interaction):
        """Activate all inactive local space corridors for moving gates across the galaxy"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            # Find all moving gates with inactive local space corridors
            inactive_corridors = self.db.execute_query(
                """SELECT c.corridor_id, l.name as gate_name, c.name as corridor_name
                   FROM corridors c
                   JOIN locations l ON c.origin_location = l.location_id
                   WHERE l.location_type = 'gate' 
                   AND l.gate_status = 'moving'
                   AND c.is_active = false
                   AND (c.name LIKE '%Local Space%' OR c.name LIKE '%Approach%' OR 
                        c.name LIKE '%Arrival%' OR c.name LIKE '%Departure%')""",
                fetch='all'
            )
            
            if not inactive_corridors:
                await interaction.followup.send("✅ All moving gates already have active local space routes.", ephemeral=False)
                return
            
            # Activate all inactive local space corridors for moving gates
            activated = self.db.execute_query(
                """UPDATE corridors SET is_active = true 
                   WHERE corridor_id IN (
                       SELECT c.corridor_id
                       FROM corridors c
                       JOIN locations l ON c.origin_location = l.location_id
                       WHERE l.location_type = 'gate' 
                       AND l.gate_status = 'moving'
                       AND c.is_active = false
                       AND (c.name LIKE '%Local Space%' OR c.name LIKE '%Approach%' OR 
                            c.name LIKE '%Arrival%' OR c.name LIKE '%Departure%')
                   )""",
            )
            
            # Get count of affected gates
            affected_gates = self.db.execute_query(
                """SELECT COUNT(DISTINCT l.location_id)
                   FROM corridors c
                   JOIN locations l ON c.origin_location = l.location_id
                   WHERE l.location_type = 'gate' 
                   AND l.gate_status = 'moving'""",
                fetch='one'
            )[0]
            
            embed = discord.Embed(
                title="🔄 Moving Gate Routes Fixed",
                description=f"Activated {len(inactive_corridors)} inactive local space corridors across {affected_gates} moving gates.",
                color=0x00ff00
            )
            
            if len(inactive_corridors) <= 10:
                # Show details if not too many
                routes_fixed = ""
                for corridor_id, gate_name, corridor_name in inactive_corridors:
                    routes_fixed += f"✅ {gate_name}: {corridor_name}\n"
                
                embed.add_field(
                    name="Routes Activated",
                    value=routes_fixed,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Scale",
                    value=f"Fixed routes for {affected_gates} moving gates across the galaxy",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            print(f"🔧 Activated {len(inactive_corridors)} inactive local space corridors for moving gates")
            
        except Exception as e:
            print(f"Error in fix_all_moving_gate_routes: {str(e)}")
            await interaction.followup.send(f"Error fixing moving gate routes: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="debug_travel_query", description="Test the exact travel query for current location")
    async def debug_travel_query(self, interaction: discord.Interaction):
        """Run the exact same query that travel.py uses to see what's wrong"""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get user's current location
            char_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_location or not char_location[0]:
                await interaction.followup.send("You don't have a current location set.", ephemeral=True)
                return
                
            current_location_id = char_location[0]
            
            # Run the EXACT same query that travel.py uses
            routes = self.db.execute_query(
                '''SELECT c.corridor_id,
                          c.name,
                          l.name AS dest_name,
                          c.travel_time,
                          c.fuel_cost,
                          l.location_type,
                          lo.location_type AS origin_type,
                          CASE WHEN lo.system_name = l.system_name THEN 1 ELSE 0 END AS same_system
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   JOIN locations lo ON c.origin_location = lo.location_id
                   WHERE c.origin_location = %s AND c.is_active = true
                   ORDER BY c.travel_time''',
                (current_location_id,),
                fetch='all'
            )
            
            location_info = self.db.execute_query(
                "SELECT name, location_type, gate_status FROM locations WHERE location_id = %s",
                (current_location_id,), fetch='one'
            )
            
            loc_name, loc_type, gate_status = location_info if location_info else ("Unknown", "Unknown", "Unknown")
            
            embed = discord.Embed(
                title=f"🔍 Travel Query Debug: {loc_name}",
                description=f"Type: {loc_type} | Status: {gate_status or 'N/A'}",
                color=0xff0000 if not routes else 0x00ff00
            )
            
            if routes:
                routes_text = ""
                for route in routes[:10]:  # Limit to 10 for display
                    corridor_id, corridor_name, dest_name, travel_time, fuel_cost, dest_type, origin_type, same_system = route
                    routes_text += f"✅ **{corridor_name}** → {dest_name} ({dest_type})\n"
                    routes_text += f"   Time: {travel_time}s | Fuel: {fuel_cost}\n\n"
                
                embed.add_field(
                    name=f"Travel Query Results ({len(routes)} found)",
                    value=routes_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Travel Query Results",
                    value="❌ No routes found by travel.py query\nThis is why you see 'No active routes from this location'",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in debug_travel_query: {str(e)}")
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="fix_broken_corridor_refs", description="Fix corridors with broken location references")
    async def fix_broken_corridor_refs(self, interaction: discord.Interaction):
        """Fix corridors that reference non-existent locations"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            # Find corridors with broken destination references
            broken_dest_corridors = self.db.execute_query(
                """SELECT c.corridor_id, c.name, c.origin_location, c.destination_location
                   FROM corridors c
                   LEFT JOIN locations l ON c.destination_location = l.location_id
                   WHERE l.location_id IS NULL AND c.is_active = true""",
                fetch='all'
            )
            
            # Find corridors with broken origin references  
            broken_origin_corridors = self.db.execute_query(
                """SELECT c.corridor_id, c.name, c.origin_location, c.destination_location
                   FROM corridors c
                   LEFT JOIN locations lo ON c.origin_location = lo.location_id
                   WHERE lo.location_id IS NULL AND c.is_active = true""",
                fetch='all'
            )
            
            total_broken = len(broken_dest_corridors) + len(broken_origin_corridors)
            
            if total_broken == 0:
                await interaction.followup.send("✅ No broken corridor references found.", ephemeral=True)
                return
            
            # Delete broken corridors
            for corridor_id, name, origin_id, dest_id in broken_dest_corridors:
                self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
                print(f"🗑️ Deleted corridor with broken destination: {name} (dest_id: {dest_id})")
                
            for corridor_id, name, origin_id, dest_id in broken_origin_corridors:
                self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
                print(f"🗑️ Deleted corridor with broken origin: {name} (origin_id: {origin_id})")
            
            # Now fix all moving gates by ensuring they have proper local connections
            moving_gates = self.db.execute_query(
                "SELECT location_id, name FROM locations WHERE location_type = 'gate' AND gate_status = 'moving'",
                fetch='all'
            )
            
            fixed_gates = 0
            for gate_id, gate_name in moving_gates:
                await self._ensure_moving_gate_local_connections(gate_id, gate_name)
                fixed_gates += 1
            
            embed = discord.Embed(
                title="🔧 Corridor References Fixed",
                description=f"Removed {total_broken} corridors with broken location references and ensured {fixed_gates} moving gates have proper connections.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="Broken References Removed",
                value=f"• {len(broken_dest_corridors)} corridors with invalid destinations\n• {len(broken_origin_corridors)} corridors with invalid origins",
                inline=False
            )
            
            embed.add_field(
                name="Moving Gates Fixed",
                value=f"Ensured {fixed_gates} moving gates have local space connections",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except Exception as e:
            print(f"Error in fix_broken_corridor_refs: {str(e)}")
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="debug_join_failure", description="Debug why the travel JOIN is failing")
    async def debug_join_failure(self, interaction: discord.Interaction):
        """Debug the exact JOIN failure in travel query"""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get user's current location
            char_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_location or not char_location[0]:
                await interaction.followup.send("You don't have a current location set.", ephemeral=True)
                return
                
            current_location_id = char_location[0]
            
            # Get raw corridors from this location
            raw_corridors = self.db.execute_query(
                "SELECT corridor_id, name, origin_location, destination_location, is_active FROM corridors WHERE origin_location = %s",
                (current_location_id,), fetch='all'
            )
            
            # Test each part of the JOIN separately
            if raw_corridors:
                test_results = []
                for corridor_id, corridor_name, origin_id, dest_id, is_active in raw_corridors:
                    # Test destination location exists
                    dest_exists = self.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = %s",
                        (dest_id,), fetch='one'
                    )
                    
                    # Test origin location exists  
                    origin_exists = self.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = %s",
                        (origin_id,), fetch='one'
                    )
                    
                    test_results.append({
                        'corridor_name': corridor_name,
                        'corridor_id': corridor_id,
                        'is_active': is_active,
                        'dest_id': dest_id,
                        'dest_exists': dest_exists[0] if dest_exists else None,
                        'origin_id': origin_id,
                        'origin_exists': origin_exists[0] if origin_exists else None
                    })
                
                result_text = ""
                for result in test_results[:5]:  # Limit to 5 for display
                    status = "✅" if result['is_active'] else "❌"
                    dest_status = "✅" if result['dest_exists'] else "❌"
                    origin_status = "✅" if result['origin_exists'] else "❌"
                    
                    result_text += f"{status} **{result['corridor_name']}**\n"
                    result_text += f"   Active: {result['is_active']} | Origin: {origin_status} | Dest: {dest_status}\n"
                    result_text += f"   Dest: {result['dest_exists'] or 'MISSING'} (ID: {result['dest_id']})\n\n"
                
                embed = discord.Embed(
                    title="🔍 JOIN Failure Debug",
                    description=f"Found {len(raw_corridors)} corridors from this location",
                    color=0xff9900
                )
                
                embed.add_field(
                    name="Corridor Analysis",
                    value=result_text,
                    inline=False
                )
                
            else:
                embed = discord.Embed(
                    title="🔍 JOIN Failure Debug", 
                    description="❌ No corridors found from this location at all",
                    color=0xff0000
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in debug_join_failure: {str(e)}")
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="create_missing_local_route", description="Create missing local space route for current moving gate")
    async def create_missing_local_route(self, interaction: discord.Interaction):
        """Create the missing local space corridor for current moving gate"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get user's current location
            char_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_location or not char_location[0]:
                await interaction.followup.send("You don't have a current location set.", ephemeral=True)
                return
                
            gate_id = char_location[0]
            
            # Get gate info
            gate_info = self.db.execute_query(
                "SELECT name, location_type, gate_status, system_name, x_coordinate, y_coordinate FROM locations WHERE location_id = %s",
                (gate_id,), fetch='one'
            )
            
            if not gate_info:
                await interaction.followup.send("Location not found.", ephemeral=True)
                return
                
            gate_name, loc_type, gate_status, system_name, gate_x, gate_y = gate_info
            
            if loc_type != 'gate' or gate_status != 'moving':
                await interaction.followup.send(f"This only works for moving gates. Current: {loc_type} ({gate_status})", ephemeral=True)
                return
            
            # Find nearest location in same system
            nearest_location = self.db.execute_query(
                """SELECT location_id, name, x_coordinate, y_coordinate,
                          ((x_coordinate - %s) * (x_coordinate - %s) + (y_coordinate - %s) * (y_coordinate - %s)) as distance_sq
                   FROM locations 
                   WHERE system_name = %s 
                   AND location_type IN ('colony', 'space_station', 'outpost')
                   AND location_id != %s
                   ORDER BY distance_sq
                   LIMIT 1""",
                (gate_x, gate_x, gate_y, gate_y, system_name, gate_id),
                fetch='one'
            )
            
            if not nearest_location:
                await interaction.followup.send(f"No major locations found in system {system_name} to connect to.", ephemeral=True)
                return
                
            loc_id, loc_name, loc_x, loc_y, distance_sq = nearest_location
            
            # Create bidirectional local space corridors
            approach_time = 180  # 3 minutes
            fuel_cost = 10
            
            # Gate to Location
            self.db.execute_query(
                """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                (f"{gate_name} - {loc_name} Departure (Local Space)", gate_id, loc_id, approach_time, fuel_cost, 'local_space')
            )
            
            # Location to Gate  
            self.db.execute_query(
                """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                (f"{loc_name} - {gate_name} Approach (Local Space)", loc_id, gate_id, approach_time, fuel_cost, 'local_space')
            )
            
            await interaction.followup.send(f"✅ Created local space routes: {gate_name} ↔ {loc_name}. Try `/travel routes` now!", ephemeral=True)
            print(f"✅ Created missing local space corridors for {gate_name}")
            
        except Exception as e:
            print(f"Error in create_missing_local_route: {str(e)}")
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="debug_gate_routes", description="Debug route visibility for current location")
    async def debug_gate_routes(self, interaction: discord.Interaction):
        """Debug why routes aren't showing for current location"""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get user's current location
            char_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_location or not char_location[0]:
                await interaction.followup.send("You don't have a current location set.", ephemeral=True)
                return
                
            location_id = char_location[0]
            
            # Get location details
            location_info = self.db.execute_query(
                "SELECT name, location_type, gate_status, system_name FROM locations WHERE location_id = %s",
                (location_id,), fetch='one'
            )
            
            if not location_info:
                await interaction.followup.send("Location not found in database.", ephemeral=True)
                return
                
            loc_name, loc_type, gate_status, system_name = location_info
            
            # Get ALL corridors from this location
            all_corridors = self.db.execute_query(
                """SELECT c.corridor_id, c.name, c.is_active, c.travel_time, c.fuel_cost, 
                          l.name as dest_name, l.location_type as dest_type
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   WHERE c.origin_location = %s
                   ORDER BY c.is_active DESC, c.name""",
                (location_id,), fetch='all'
            )
            
            # Get what travel.py would find (only active)
            travel_corridors = self.db.execute_query(
                """SELECT c.corridor_id, c.name, c.travel_time, c.fuel_cost,
                          l.name as dest_name, l.location_type as dest_type
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   WHERE c.origin_location = %s AND c.is_active = true
                   ORDER BY c.travel_time""",
                (location_id,), fetch='all'
            )
            
            embed = discord.Embed(
                title=f"🔍 Route Debug: {loc_name}",
                description=f"Type: {loc_type} | Status: {gate_status or 'N/A'} | System: {system_name}",
                color=0xffaa00
            )
            
            # All corridors section
            if all_corridors:
                all_routes_text = ""
                for corridor_id, name, is_active, travel_time, fuel_cost, dest_name, dest_type in all_corridors:
                    status_icon = "✅" if is_active else "❌"
                    all_routes_text += f"{status_icon} **{name}** → {dest_name} ({dest_type})\n"
                    all_routes_text += f"   Time: {travel_time}s | Fuel: {fuel_cost} | Active: {is_active}\n\n"
                
                if len(all_routes_text) > 1024:
                    all_routes_text = all_routes_text[:1000] + "...\n(truncated)"
                    
                embed.add_field(
                    name=f"All Corridors ({len(all_corridors)} total)",
                    value=all_routes_text or "None found",
                    inline=False
                )
            else:
                embed.add_field(
                    name="All Corridors",
                    value="❌ No corridors found from this location",
                    inline=False
                )
            
            # What travel.py sees
            if travel_corridors:
                travel_routes_text = ""
                for corridor_id, name, travel_time, fuel_cost, dest_name, dest_type in travel_corridors:
                    travel_routes_text += f"✅ **{name}** → {dest_name} ({dest_type})\n"
                    travel_routes_text += f"   Time: {travel_time}s | Fuel: {fuel_cost}\n\n"
                
                if len(travel_routes_text) > 1024:
                    travel_routes_text = travel_routes_text[:1000] + "...\n(truncated)"
                    
                embed.add_field(
                    name=f"Travel Command Sees ({len(travel_corridors)} active)",
                    value=travel_routes_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Travel Command Sees",
                    value="❌ No active corridors found (this is why no routes show!)",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in debug_gate_routes: {str(e)}")
            await interaction.followup.send(f"Error debugging routes: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="fix_gate_architecture", description="Fix existing galaxy to use proper local space connections")
    async def fix_gate_architecture(self, interaction: discord.Interaction):
        """Fix existing galaxy to use proper Major Location -> Local Space -> Gate architecture"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            print("🔧 Starting COMPREHENSIVE gate architecture fix...")
            
            # Use the new shared architecture validator
            from utils.architecture_validator import ArchitectureValidator
            validator = ArchitectureValidator(self.db)
            fixes = await validator.validate_and_fix_architecture(silent=False)
            
            # Build response embed
            total_fixes = sum(fixes.values())
            
            if total_fixes == 0:
                embed = discord.Embed(
                    title="✅ Gate Architecture Already Correct",
                    description="No architectural violations found. Galaxy follows proper gate architecture.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="🔧 Gate Architecture Fix Complete",
                    description=f"Successfully processed {total_fixes} architectural violations",
                    color=0x00ff00
                )
                
                embed.add_field(
                    name="🛠️ Architecture Fixes Applied",
                    value=f"• Removed {fixes['cross_system_removed']} cross-system violations\n"
                          f"• Fixed {fixes['major_to_gate_fixed']} major ↔ gate connections\n"
                          f"• Removed {fixes['major_to_major_removed']} major-to-major gated routes\n"
                          f"• Created {fixes['missing_local_created']} missing local connections\n"
                          f"• Fixed {fixes['unused_gate_fixed']} unused gate violations\n"
                          f"• Fixed {fixes['moving_gate_fixed']} moving gate violations\n"
                          f"• Fixed {fixes['active_gate_fixed']} active gate violations\n"
                          f"• Removed {fixes['gated_violations_removed']} gated architectural violations",
                    inline=False
                )
                
                embed.add_field(
                    name="🌐 Proper Architecture",
                    value="**Major Locations** → **Local Space** (🌌) → **Gates** → **Gated Corridors** (🔵) → **Gates** → **Local Space** (🌌) → **Major Locations**\n\n"
                          "*Major locations can only connect to gates via local space routes (danger level 1)*",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"🎉 Gate architecture fix completed: {total_fixes} total fixes")
            
        except Exception as e:
            print(f"Error in fix_gate_architecture: {str(e)}")
            await interaction.followup.send(f"Error fixing gate architecture: {str(e)}", ephemeral=True)

    @galaxy_group.command(name="fix_corridor_types", description="Validate and fix corridor type classifications")
    async def fix_corridor_types(self, interaction: discord.Interaction):
        """Fix misclassified corridor types based on location rules"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            print("🔧 Starting corridor type validation and fixes...")
            
            # Run the corridor classification fix
            self.db._classify_existing_corridors()
            
            # Get statistics after fix
            type_counts = self.db.execute_query("""
                SELECT corridor_type, COUNT(*) as count
                FROM corridors 
                WHERE is_active = true
                GROUP BY corridor_type
            """, fetch='all')
            
            # Build response embed
            embed = discord.Embed(
                title="🔧 Corridor Type Validation Complete",
                description="Validated and corrected corridor type classifications based on location rules",
                color=0x00ff00
            )
            
            if type_counts:
                type_summary = '\n'.join([f"• **{corridor_type.title()}**: {count}" for corridor_type, count in type_counts])
                embed.add_field(
                    name="📊 Current Corridor Distribution",
                    value=type_summary,
                    inline=False
                )
            
            embed.add_field(
                name="✅ Rules Applied",
                value="• Major locations ↔ local gates = `local_space`\n"
                      "• Gates in different systems = `gated`\n"
                      "• Gates in same system = `local_space`\n"
                      "• Major locations to major locations = `ungated`\n"
                      "• Name-based detection for local space routes",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Route Legend",
                value="🌌 Local Space • 🔵 Gated • ⭕ Ungated",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print("🎉 Corridor type validation completed successfully")
            
        except Exception as e:
            print(f"Error in fix_corridor_types: {str(e)}")
            await interaction.followup.send(f"Error fixing corridor types: {str(e)}", ephemeral=True)

    async def _fix_cross_system_violations(self, fixes):
        """Remove any connections that violate system-based architecture"""
        # Remove cross-system major↔gate connections
        cross_system_violations = self.db.execute_query(
            """SELECT c.corridor_id, c.name, lo.name as origin_name, ld.name as dest_name,
                      lo.location_type as origin_type, ld.location_type as dest_type
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND lo.system_name != ld.system_name
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        
        for corridor_id, name, origin_name, dest_name, origin_type, dest_type in cross_system_violations:
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
            fixes['cross_system_removed'] += 1
            connection_type = f"{origin_type} ↔ {dest_type}"
            print(f"🗑️ Removed cross-system violation: {name} - {connection_type} ({origin_name} → {dest_name})")

    async def _ensure_local_space_connections(self, fixes):
        """Ensure all major locations have proper local space connections to gates in their system"""
        # Get all systems and their major locations and gates
        systems_data = self.db.execute_query(
            """SELECT DISTINCT l.system_name,
                      GROUP_CONCAT(CASE WHEN l.location_type IN ('colony', 'space_station', 'outpost') 
                                        THEN l.location_id || ':' || l.name END) as majors,
                      GROUP_CONCAT(CASE WHEN l.location_type = 'gate' 
                                        THEN l.location_id || ':' || l.name || ':' || l.gate_status END) as gates
               FROM locations l
               WHERE l.system_name IS NOT NULL 
               AND l.location_type IN ('colony', 'space_station', 'outpost', 'gate')
               GROUP BY l.system_name
               HAVING majors IS NOT NULL AND gates IS NOT NULL""",
            fetch='all'
        )
        
        for system_name, majors_str, gates_str in systems_data:
            if not majors_str or not gates_str:
                continue
                
            # Parse major locations
            majors = []
            for major_data in majors_str.split(','):
                if ':' in major_data:
                    major_id, major_name = major_data.split(':', 1)
                    majors.append((int(major_id), major_name))
            
            # Parse gates
            gates = []
            for gate_data in gates_str.split(','):
                if gate_data.count(':') >= 2:
                    parts = gate_data.split(':', 2)
                    gate_id, gate_name, gate_status = int(parts[0]), parts[1], parts[2]
                    gates.append((gate_id, gate_name, gate_status))
            
            # Ensure each major location connects to each gate via local space
            for major_id, major_name in majors:
                for gate_id, gate_name, gate_status in gates:
                    await self._ensure_local_connection_exists(major_id, major_name, gate_id, gate_name, fixes)

    async def _ensure_local_connection_exists(self, major_id, major_name, gate_id, gate_name, fixes):
        """Ensure a local space connection exists between major location and gate"""
        # Check if connection already exists
        existing = self.db.execute_query(
            """SELECT corridor_id, danger_level, travel_time FROM corridors 
               WHERE ((origin_location = %s AND destination_location = %s) OR
                      (origin_location = %s AND destination_location = %s))
               AND corridor_type != 'ungated'""",
            (major_id, gate_id, gate_id, major_id),
            fetch='one'
        )
        
        if existing:
            corridor_id, danger_level, travel_time = existing
            # Fix existing connection to be proper local space
            if danger_level > 1 or travel_time > 300:
                target_danger = 1
                target_time = min(travel_time, 300)
                
                self.db.execute_query(
                    """UPDATE corridors 
                       SET danger_level = %s, travel_time = %s
                       WHERE corridor_id = %s""",
                    (target_danger, target_time, corridor_id)
                )
                fixes['major_to_gate_fixed'] += 1
                print(f"✅ Fixed local connection: {major_name} ↔ {gate_name} (danger: {danger_level}→{target_danger}, time: {travel_time}→{target_time})")
        else:
            # Create missing local space connection
            approach_time = random.randint(120, 300)  # 2-5 minutes
            fuel_cost = random.randint(5, 15)
            
            # Create bidirectional local space corridors
            self.db.execute_query(
                """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                (f"{major_name} - {gate_name} Approach (Local Space)", major_id, gate_id, approach_time, fuel_cost, 'local_space')
            )
            
            self.db.execute_query(
                """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                (f"{gate_name} - {major_name} Departure (Local Space)", gate_id, major_id, approach_time, fuel_cost, 'local_space')
            )
            
            fixes['missing_local_created'] += 2
            print(f"➕ Created local connection: {major_name} ↔ {gate_name} (local space)")

    async def _fix_gate_connectivity_by_status(self, fixes):
        """Fix gate connectivity based on their status (active/unused/moving)"""
        # Get all gates with their current connections
        gates_data = self.db.execute_query(
            """SELECT l.location_id, l.name, l.gate_status,
                      COUNT(CASE WHEN c.corridor_type = 'gated' THEN 1 END) as gated_connections,
                      COUNT(CASE WHEN c.corridor_type = 'local_space' THEN 1 END) as local_connections
               FROM locations l
               LEFT JOIN corridors c ON (c.origin_location = l.location_id OR c.destination_location = l.location_id)
               WHERE l.location_type = 'gate'
               GROUP BY l.location_id, l.name, l.gate_status""",
            fetch='all'
        )
        
        for gate_id, gate_name, gate_status, gated_connections, local_connections in gates_data:
            if gate_status == 'unused':
                # Unused gates should have ONLY local connections (max 1 system's worth)
                if gated_connections > 0:
                    await self._remove_gate_gated_connections(gate_id, gate_name)
                    fixes['unused_gate_fixed'] += gated_connections
                    print(f"🔧 Fixed unused gate {gate_name}: removed {gated_connections} gated connections")
                    
            elif gate_status == 'moving':
                # Moving gates should have local connections but no gated connections (will get them when active)
                if gated_connections > 0:
                    await self._remove_gate_gated_connections(gate_id, gate_name)
                    fixes['moving_gate_fixed'] += gated_connections
                    print(f"🔧 Fixed moving gate {gate_name}: removed {gated_connections} gated connections")
                
                # Ensure moving gate has local space connections
                await self._ensure_moving_gate_local_connections(gate_id, gate_name)
                    
            elif gate_status == 'active':
                # Active gates should have both local connections AND gated connections to other active gates
                # Ensure this active gate has proper gated connections
                fixed_count = await self._ensure_active_gate_connections(gate_id, gate_name, gated_connections)
                fixes['active_gate_fixed'] += fixed_count

    async def _remove_gate_gated_connections(self, gate_id, gate_name):
        """Remove all gated connections from a gate (keep only local space)"""
        gated_corridors = self.db.execute_query(
            """SELECT corridor_id FROM corridors 
               WHERE (origin_location = %s OR destination_location = %s)
               AND name NOT LIKE '%Local Space%' 
               AND name NOT LIKE '%Approach%' 
               AND name NOT LIKE '%Arrival%' 
               AND name NOT LIKE '%Departure%'
               AND corridor_type != 'ungated'""",
            (gate_id, gate_id),
            fetch='all'
        )
        
        for (corridor_id,) in gated_corridors:
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))

    async def _ensure_moving_gate_local_connections(self, gate_id, gate_name):
        """Ensure a moving gate has active local space connections to nearby locations"""
        # Find nearby major locations in the same system
        gate_info = self.db.execute_query(
            "SELECT system_name, x_coordinate, y_coordinate FROM locations WHERE location_id = %s",
            (gate_id,), fetch='one'
        )
        
        if not gate_info:
            return
            
        system_name, gate_x, gate_y = gate_info
        
        # Find major locations in the same system
        nearby_locations = self.db.execute_query(
            """SELECT location_id, name, x_coordinate, y_coordinate,
                      ((x_coordinate - %s) * (x_coordinate - %s) + (y_coordinate - %s) * (y_coordinate - %s)) as distance_sq
               FROM locations 
               WHERE system_name = %s 
               AND location_type IN ('colony', 'space_station', 'outpost')
               ORDER BY distance_sq
               LIMIT 3""",
            (gate_x, gate_x, gate_y, gate_y, system_name),
            fetch='all'
        )
        
        # Create local space connections to nearby locations if they don't exist
        for loc_id, loc_name, loc_x, loc_y, distance_sq in nearby_locations:
            # Check if FROM gate connection exists (this is what's missing!)
            gate_to_loc_exists = self.db.execute_query(
                """SELECT corridor_id FROM corridors 
                   WHERE origin_location = %s AND destination_location = %s AND is_active = true""",
                (gate_id, loc_id),
                fetch='one'
            )
            
            # Check if TO gate connection exists  
            loc_to_gate_exists = self.db.execute_query(
                """SELECT corridor_id FROM corridors 
                   WHERE origin_location = %s AND destination_location = %s AND is_active = true""",
                (loc_id, gate_id),
                fetch='one'
            )
            
            # Create FROM gate connection if missing
            if not gate_to_loc_exists:
                approach_time = random.randint(120, 300)  # 2-5 minutes
                fuel_cost = random.randint(5, 15)
                
                self.db.execute_query(
                    """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                    (f"{gate_name} - {loc_name} Departure (Local Space)", gate_id, loc_id, approach_time, fuel_cost, 'local_space')
                )
                print(f"  ✅ Created FROM gate route: {gate_name} → {loc_name}")
            
            # Create TO gate connection if missing
            if not loc_to_gate_exists:
                approach_time = random.randint(120, 300)  # 2-5 minutes
                fuel_cost = random.randint(5, 15)
                
                self.db.execute_query(
                    """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, 1, %s, TRUE, TRUE)""",
                    (f"{loc_name} - {gate_name} Approach (Local Space)", loc_id, gate_id, approach_time, fuel_cost, 'local_space')
                )
                print(f"  ✅ Created TO gate route: {loc_name} → {gate_name}")

    async def _ensure_active_gate_connections(self, gate_id, gate_name, current_gated_connections):
        """Ensure an active gate has proper gated connections to other active gates"""
        fixes_made = 0
        
        # Active gates should have at least 1-3 gated connections to other active gates
        if current_gated_connections < 1:
            # Find nearby active gates to connect to
            gate_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate FROM locations WHERE location_id = %s",
                (gate_id,), fetch='one'
            )
            
            if not gate_info:
                return fixes_made
                
            gate_x, gate_y = gate_info
            
            # Find nearby active gates (not including this one)
            nearby_gates = self.db.execute_query(
                """SELECT location_id, name, x_coordinate, y_coordinate 
                   FROM locations 
                   WHERE location_type = 'gate' 
                   AND gate_status = 'active' 
                   AND location_id != %s
                   ORDER BY ((x_coordinate - %s) * (x_coordinate - %s) + (y_coordinate - %s) * (y_coordinate - %s))
                   LIMIT 3""",
                (gate_id, gate_x, gate_x, gate_y, gate_y),
                fetch='all'
            )
            
            # Create gated connections to the nearest active gates
            for target_id, target_name, target_x, target_y in nearby_gates:
                # Check if bidirectional corridors already exist
                forward_exists = self.db.execute_query(
                    """SELECT corridor_id FROM corridors 
                       WHERE origin_location = %s AND destination_location = %s
                       AND name NOT LIKE '%Local Space%'""",
                    (gate_id, target_id), fetch='one'
                )
                
                backward_exists = self.db.execute_query(
                    """SELECT corridor_id FROM corridors 
                       WHERE origin_location = %s AND destination_location = %s
                       AND name NOT LIKE '%Local Space%'""",
                    (target_id, gate_id), fetch='one'
                )
                
                # Calculate distance and travel time
                distance = ((target_x - gate_x) ** 2 + (target_y - gate_y) ** 2) ** 0.5
                travel_time = max(300, int(distance * 2))  # At least 5 minutes, scale with distance
                fuel_cost = max(50, int(distance * 0.5))  # Scale fuel with distance
                
                # Create forward corridor if missing
                if not forward_exists:
                    self.db.execute_query(
                        """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                           VALUES (%s, %s, %s, %s, %s, 2, %s, TRUE, TRUE)""",
                        (f"{gate_name} - {target_name} Corridor", gate_id, target_id, travel_time, fuel_cost, 'gated')
                    )
                    fixes_made += 1
                    print(f"🔧 Fixed active gate {gate_name}: created gated connection to {target_name}")
                
                # Create backward corridor if missing
                if not backward_exists:
                    self.db.execute_query(
                        """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_active, is_generated)
                           VALUES (%s, %s, %s, %s, %s, 2, %s, TRUE, TRUE)""",
                        (f"{target_name} - {gate_name} Corridor", target_id, gate_id, travel_time, fuel_cost, 'gated')
                    )
                    fixes_made += 1
                    print(f"🔧 Fixed active gate {gate_name}: created return gated connection from {target_name}")
                
                # Stop after creating connections to avoid over-connecting
                if fixes_made >= 2:  # Forward + backward to one gate is enough
                    break
        
        return fixes_made

    async def _remove_major_to_major_gated(self, fixes):
        """Remove direct gated connections between major locations (keep ungated only)"""
        major_to_major_gated = self.db.execute_query(
            """SELECT c.corridor_id, c.name, lo.name as origin_name, ld.name as dest_name
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE lo.location_type IN ('colony', 'space_station', 'outpost')
               AND ld.location_type IN ('colony', 'space_station', 'outpost')
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        
        for corridor_id, name, origin_name, dest_name in major_to_major_gated:
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
            fixes['major_to_major_removed'] += 1
            print(f"🗑️ Removed major-to-major gated: {name} ({origin_name} → {dest_name})")

    async def _remove_gated_major_to_gate(self, fixes):
        """Remove any direct gated connections from major locations to gates"""
        gated_major_to_gate = self.db.execute_query(
            """SELECT c.corridor_id, c.name, lo.name as origin_name, ld.name as dest_name,
                      lo.location_type as origin_type, ld.location_type as dest_type
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND c.name NOT LIKE '%Local Space%' 
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        
        for corridor_id, name, origin_name, dest_name, origin_type, dest_type in gated_major_to_gate:
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
            fixes['gated_violations_removed'] += 1
            connection_type = f"{origin_type} ↔ {dest_type}"
            print(f"🗑️ Removed gated major-gate connection: {name} - {connection_type} ({origin_name} → {dest_name})")

    async def _detect_architecture_violations(self):
        """Detect and return comprehensive architecture violations"""
        violations = {
            'cross_system_connections': [],
            'major_to_major_gated': [],
            'major_to_gate_gated': [],
            'unused_gate_violations': [],
            'moving_gate_violations': [],
            'missing_local_connections': []
        }
        
        # Detect cross-system major↔gate connections
        cross_system = self.db.execute_query(
            """SELECT c.name, lo.name as origin_name, ld.name as dest_name,
                      lo.location_type as origin_type, ld.location_type as dest_type,
                      lo.system_name as origin_system, ld.system_name as dest_system
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND lo.system_name != ld.system_name
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        violations['cross_system_connections'] = cross_system
        
        # Detect major-to-major gated connections
        major_to_major = self.db.execute_query(
            """SELECT c.name, lo.name as origin_name, ld.name as dest_name
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE lo.location_type IN ('colony', 'space_station', 'outpost')
               AND ld.location_type IN ('colony', 'space_station', 'outpost')
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        violations['major_to_major_gated'] = major_to_major
        
        # Detect major-to-gate gated connections (should be local space only)
        major_to_gate_gated = self.db.execute_query(
            """SELECT c.name, lo.name as origin_name, ld.name as dest_name,
                      lo.location_type as origin_type, ld.location_type as dest_type
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND c.danger_level > 1
               AND c.name NOT LIKE '%Local Space%' 
               AND c.name NOT LIKE '%Approach%' 
               AND c.name NOT LIKE '%Arrival%' 
               AND c.name NOT LIKE '%Departure%'
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        violations['major_to_gate_gated'] = major_to_gate_gated
        
        # Detect unused gate violations (should have only local connections)
        unused_gate_violations = self.db.execute_query(
            """SELECT l.name as gate_name, COUNT(*) as gated_connections
               FROM locations l
               JOIN corridors c ON (c.origin_location = l.location_id OR c.destination_location = l.location_id)
               WHERE l.location_type = 'gate' AND l.gate_status = 'unused'
               AND c.name NOT LIKE '%Local Space%' AND c.name NOT LIKE '%Approach%' 
               AND c.name NOT LIKE '%Arrival%' AND c.name NOT LIKE '%Departure%'
               AND c.corridor_type != 'ungated'
               GROUP BY l.location_id, l.name
               HAVING gated_connections > 0""",
            fetch='all'
        )
        violations['unused_gate_violations'] = unused_gate_violations
        
        # Detect moving gate violations (should have only local connections)
        moving_gate_violations = self.db.execute_query(
            """SELECT l.name as gate_name, COUNT(*) as gated_connections
               FROM locations l
               JOIN corridors c ON (c.origin_location = l.location_id OR c.destination_location = l.location_id)
               WHERE l.location_type = 'gate' AND l.gate_status = 'moving'
               AND c.name NOT LIKE '%Local Space%' AND c.name NOT LIKE '%Approach%' 
               AND c.name NOT LIKE '%Arrival%' AND c.name NOT LIKE '%Departure%'
               AND c.corridor_type != 'ungated'
               GROUP BY l.location_id, l.name
               HAVING gated_connections > 0""",
            fetch='all'
        )
        violations['moving_gate_violations'] = moving_gate_violations
        
        return violations

    async def _ensure_system_local_connections(self):
        """Ensure all systems have proper local space connections between majors and gates"""
        systems_needing_connections = []
        
        # Get all systems and check their internal connectivity
        systems = self.db.execute_query(
            """SELECT DISTINCT system_name FROM locations 
               WHERE system_name IS NOT NULL 
               AND location_type IN ('colony', 'space_station', 'outpost', 'gate')""",
            fetch='all'
        )
        
        for (system_name,) in systems:
            # Get majors and gates in this system
            locations = self.db.execute_query(
                """SELECT location_id, name, location_type FROM locations
                   WHERE system_name = %s 
                   AND location_type IN ('colony', 'space_station', 'outpost', 'gate')""",
                (system_name,),
                fetch='all'
            )
            
            majors = [(lid, name) for lid, name, ltype in locations if ltype in ('colony', 'space_station', 'outpost')]
            gates = [(lid, name) for lid, name, ltype in locations if ltype == 'gate']
            
            missing_connections = []
            
            # Check if each major connects to each gate via local space
            for major_id, major_name in majors:
                for gate_id, gate_name in gates:
                    connection_exists = self.db.execute_query(
                        """SELECT COUNT(*) FROM corridors 
                           WHERE ((origin_location = %s AND destination_location = %s) OR
                                  (origin_location = %s AND destination_location = %s))
                           AND (danger_level = 1 OR corridor_type = 'local_space')
                           AND corridor_type != 'ungated'""",
                        (major_id, gate_id, gate_id, major_id),
                        fetch='one'
                    )[0]
                    
                    if connection_exists == 0:
                        missing_connections.append((major_name, gate_name))
            
            if missing_connections:
                systems_needing_connections.append((system_name, missing_connections))
        
        return systems_needing_connections
        
    @galaxy_group.command(name="shift_corridors", description="Trigger corridor shifts to change galaxy connectivity")
    @app_commands.describe(
        intensity="Intensity of the shift (1-5, higher = more changes)",
        target_region="Focus shifts on a specific region (optional)"
    )
    async def shift_corridors(self, interaction: discord.Interaction, 
                             intensity: int = 2, target_region: str = None):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        if intensity < 1 or intensity > 5:
            await interaction.response.send_message("Intensity must be between 1 and 5.", ephemeral=True)
            return
        
        # Create shift type selection dropdown
        shift_options = [
            discord.SelectOption(
                label="Mixed Shift", 
                value="mixed",
                description="All types: route changes, shuffles, and new routes",
                emoji="🌌"
            ),
            discord.SelectOption(
                label="Destination Shuffle", 
                value="shuffle",
                description="Change where existing corridors lead",
                emoji="🔀"
            ),
            discord.SelectOption(
                label="Route Changes", 
                value="routes",
                description="Open/close existing corridor routes",
                emoji="🚧"
            ),
            discord.SelectOption(
                label="New Routes", 
                value="new",
                description="Create new dormant corridor possibilities",
                emoji="✨"
            )
        ]
        
        class ShiftTypeSelect(discord.ui.Select):
            def __init__(self, cog_ref, intensity_val, target_region_val):
                super().__init__(placeholder="Choose shift type...", options=shift_options)
                self.cog = cog_ref
                self.intensity = intensity_val
                self.target_region = target_region_val
            
            async def callback(self, select_interaction: discord.Interaction):
                await select_interaction.response.defer()
                
                try:
                    await select_interaction.edit_original_response(content="Processing corridor shift...", view=None)
                    
                    shift_results = await self.cog._execute_corridor_shifts(
                        self.intensity, self.target_region, self.values[0]
                    )
                    
                    embed = discord.Embed(
                        title="🌌 Corridor Shift Complete",
                        description=f"Galactic infrastructure has undergone changes (Intensity {self.intensity}, Type: {self.values[0].title()})",
                        color=0x4B0082
                    )
                    
                    if shift_results['activated']:
                        embed.add_field(
                            name="🟢 New Corridors Activated",
                            value=f"{shift_results['activated']} dormant routes opened",
                            inline=True
                        )
                    
                    if shift_results['deactivated']:
                        embed.add_field(
                            name="🔴 Corridors Collapsed", 
                            value=f"{shift_results['deactivated']} active routes closed",
                            inline=True
                        )
                    
                    if shift_results['new_dormant']:
                        embed.add_field(
                            name="🌫️ New Potential Routes",
                            value=f"{shift_results['new_dormant']} dormant corridors formed",
                            inline=True
                        )
                    
                    if shift_results.get('destinations_changed', 0):
                        embed.add_field(
                            name="🔀 Routes Redirected",
                            value=f"{shift_results['destinations_changed']} corridors lead to new destinations",
                            inline=True
                        )
                    
                    connectivity_status = await self.cog._analyze_connectivity_post_shift()
                    embed.add_field(
                        name="📊 Connectivity Status",
                        value=connectivity_status,
                        inline=False
                    )
                    
                    embed.add_field(
                        name="⚠️ Advisory",
                        value="Players in transit may experience route changes. Check `/travel routes` for updates.",
                        inline=False
                    )
                    
                    await select_interaction.edit_original_response(content=None, embed=embed, view=None)
                    
                    # Check for moving gates that should reconnect
                    await self.cog._check_and_reconnect_moving_gates()
                    
                    # Notify active travelers
                    await self.cog._notify_travelers_of_shifts(shift_results)
                    news_cog = self.cog.bot.get_cog('GalacticNewsCog')
                    if news_cog:
                        await news_cog.post_corridor_shift_news(shift_results, self.intensity)  
                    
                except Exception as e:
                    await select_interaction.edit_original_response(content=f"Error during corridor shift: {str(e)}", view=None)
        
        class ShiftView(discord.ui.View):
            def __init__(self, cog_ref, intensity_val, target_region_val):
                super().__init__(timeout=60)
                self.add_item(ShiftTypeSelect(cog_ref, intensity_val, target_region_val))
        
        # Send initial message with dropdown
        await interaction.response.send_message(
            "Select the type of corridor shift to perform:",
            view=ShiftView(self, intensity, target_region),
            ephemeral=True
        )

    @galaxy_group.command(name="force_gate_check", description="Force immediate gate status update and reconnection check")
    async def force_gate_check(self, interaction: discord.Interaction):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            results = {
                'reconnected_gates': 0,
                'started_moving': 0,
                'gates_processed': []
            }
            
            # Check and reconnect moving gates
            moving_gates = self.db.execute_query(
                """SELECT location_id, name, reconnection_eta 
                   FROM locations 
                   WHERE location_type = 'gate' 
                   AND gate_status = 'moving' 
                   AND reconnection_eta IS NOT NULL 
                   AND reconnection_eta <= NOW()""",
                fetch='all'
            )
            
            for gate in moving_gates:
                gate_id, gate_name, _ = gate
                
                # Update gate status back to active and restore services
                self.db.execute_query(
                    """UPDATE locations SET 
                       gate_status = 'active', 
                       reconnection_eta = NULL,
                       has_shops = true,
                       has_medical = true, 
                       has_repairs = true,
                       has_fuel = true,
                       population = %s
                       WHERE location_id = %s""",
                    (random.randint(50, 150), gate_id)
                )
                
                # Find nearest major location for reconnection
                nearest_major = self.db.execute_query(
                    """SELECT l2.location_id, l2.name, l2.x_coordinate, l2.y_coordinate,
                              SQRT((l1.x_coordinate - l2.x_coordinate) * (l1.x_coordinate - l2.x_coordinate) + 
                                   (l1.y_coordinate - l2.y_coordinate) * (l1.y_coordinate - l2.y_coordinate)) as distance
                       FROM locations l1
                       JOIN locations l2 ON l2.location_type IN ('colony', 'space_station', 'outpost')
                       WHERE l1.location_id = %s
                       AND l2.gate_status = 'active'
                       ORDER BY distance LIMIT 1""",
                    (gate_id,),
                    fetch='one'
                )
                
                if nearest_major:
                    # Reactivate any deactivated corridors from when it became moving
                    self.db.execute_query(
                        """UPDATE corridors SET is_active = true 
                           WHERE (origin_location = %s OR destination_location = %s)
                           AND is_active = false""",
                        (gate_id, gate_id)
                    )
                
                results['reconnected_gates'] += 1
                results['gates_processed'].append(f"🟢 {gate_name} reconnected to network")
            
            # Check for long-abandoned gates that can start moving
            long_abandoned_gates = self.db.execute_query(
                """SELECT location_id, name, abandoned_since 
                   FROM locations 
                   WHERE location_type = 'gate' 
                   AND gate_status = 'unused' 
                   AND abandoned_since IS NOT NULL 
                   AND abandoned_since <= NOW() - INTERVAL '3 days'""",
                fetch='all'
            )
            
            for gate in long_abandoned_gates:
                gate_id, gate_name, _ = gate
                
                # 10% chance that an abandoned gate starts moving
                if random.random() < 0.1:
                    # Calculate reconnection time (4-24 hours from now)
                    hours_until_reconnection = random.randint(4, 24)
                    reconnection_time = datetime.now() + timedelta(hours=hours_until_reconnection)
                    
                    self.db.execute_query(
                        """UPDATE locations SET 
                           gate_status = 'moving',
                           reconnection_eta = %s,
                           abandoned_since = NULL
                           WHERE location_id = %s""",
                        (reconnection_time, gate_id)
                    )
                    
                    # Ensure moving gate has local space connections
                    await self._ensure_moving_gate_local_connections(gate_id, gate_name)
                    
                    results['started_moving'] += 1
                    results['gates_processed'].append(f"🔄 {gate_name} started moving - will reconnect in {hours_until_reconnection} hours")
            
            # Create response embed
            embed = discord.Embed(
                title="🔄 Gate Status Check Complete",
                description="Forced gate status update has been completed",
                color=0x00FF00
            )
            
            if results['reconnected_gates'] > 0:
                embed.add_field(
                    name="🟢 Gates Reconnected",
                    value=f"{results['reconnected_gates']} moving gates returned to active status",
                    inline=True
                )
            
            if results['started_moving'] > 0:
                embed.add_field(
                    name="🔄 Gates Started Moving", 
                    value=f"{results['started_moving']} abandoned gates began relocation",
                    inline=True
                )
            
            if not results['gates_processed']:
                embed.add_field(
                    name="ℹ️ Status",
                    value="No gates required status updates at this time",
                    inline=False
                )
            else:
                # Show first few processed gates
                status_list = results['gates_processed'][:5]
                if len(results['gates_processed']) > 5:
                    status_list.append(f"... and {len(results['gates_processed']) - 5} more")
                
                embed.add_field(
                    name="📋 Gates Processed",
                    value="\n".join(status_list),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error during gate check: {str(e)}")

    @galaxy_group.command(name="debug_gates", description="Display gate status information with pagination")
    @app_commands.describe(
        status="Filter by gate status (active/moving/unused/all)",
        page="Page number to display (20 gates per page)"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="All Gates", value="all"),
        app_commands.Choice(name="Active Gates", value="active"),
        app_commands.Choice(name="Moving Gates", value="moving"), 
        app_commands.Choice(name="Unused/Abandoned Gates", value="unused")
    ])
    async def debug_gates(self, interaction: discord.Interaction, status: str = "all", page: int = 1):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Build query based on status filter
            base_query = """
                SELECT l.location_id, l.name, l.x_coordinate, l.y_coordinate, l.gate_status, 
                       l.reconnection_eta, l.abandoned_since, l.population,
                       COUNT(c.corridor_id) as connected_routes
                FROM locations l
                LEFT JOIN corridors c ON (c.origin_location = l.location_id OR c.destination_location = l.location_id) 
                                      AND c.is_active = true
                WHERE l.location_type = 'gate'
            """
            
            params = []
            if status != "all":
                base_query += " AND l.gate_status = %s"
                params.append(status)
            
            base_query += """
                GROUP BY l.location_id, l.name, l.x_coordinate, l.y_coordinate, l.gate_status, 
                         l.reconnection_eta, l.abandoned_since, l.population
                ORDER BY l.gate_status, l.name
            """
            
            # Get all matching gates
            all_gates = self.db.execute_query(base_query, params, fetch='all')
            
            if not all_gates:
                embed = discord.Embed(
                    title="🚪 Gate Debug - No Results",
                    description=f"No gates found matching status filter: **{status}**",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Calculate pagination
            gates_per_page = 20
            total_gates = len(all_gates)
            total_pages = (total_gates + gates_per_page - 1) // gates_per_page
            
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages
            
            start_idx = (page - 1) * gates_per_page
            end_idx = min(start_idx + gates_per_page, total_gates)
            page_gates = all_gates[start_idx:end_idx]
            
            # Count gates by status for summary
            status_counts = {'active': 0, 'moving': 0, 'unused': 0}
            for gate in all_gates:
                gate_status = gate[4]  # gate_status column
                if gate_status in status_counts:
                    status_counts[gate_status] += 1
            
            # Create embed
            embed = discord.Embed(
                title=f"🚪 Gate Debug - {status.title()} Gates",
                description=f"Showing {len(page_gates)} gates (Page {page}/{total_pages})",
                color=0x4B0082
            )
            
            # Add summary statistics
            summary_text = f"**Total Gates:** {total_gates}\n"
            summary_text += f"🟢 Active: {status_counts['active']} | "
            summary_text += f"🔄 Moving: {status_counts['moving']} | "
            summary_text += f"⚫ Unused: {status_counts['unused']}"
            
            embed.add_field(
                name="📊 Summary",
                value=summary_text,
                inline=False
            )
            
            # Display gates for this page
            gate_lines = []
            for gate in page_gates:
                (gate_id, gate_name, x_coordinate, y_coordinate, gate_status, 
                 reconnection_eta, abandoned_since, population, connected_routes) = gate
                
                # Format status indicator
                if gate_status == 'active':
                    status_icon = "🟢"
                elif gate_status == 'moving':
                    status_icon = "🔄"
                else:  # unused
                    status_icon = "⚫"
                
                # Format additional info based on status
                extra_info = ""
                if gate_status == 'moving' and reconnection_eta:
                    try:
                        eta = safe_datetime_parse(reconnection_eta.replace('Z', '+00:00'))
                        time_remaining = eta - datetime.now()
                        if time_remaining.total_seconds() > 0:
                            hours_remaining = int(time_remaining.total_seconds() // 3600)
                            extra_info = f" (ETA: {hours_remaining}h)"
                        else:
                            extra_info = " (Ready to reconnect)"
                    except:
                        extra_info = " (ETA: Unknown)"
                elif gate_status == 'unused' and abandoned_since:
                    try:
                        abandoned = safe_datetime_parse(abandoned_since.replace('Z', '+00:00'))
                        time_abandoned = datetime.now() - abandoned
                        days_abandoned = int(time_abandoned.total_seconds() // 86400)
                        extra_info = f" ({days_abandoned}d ago)"
                    except:
                        extra_info = " (Recently)"
                
                # Format line
                gate_line = f"{status_icon} **{gate_name}**{extra_info}"
                gate_line += f"\n   └ Routes: {connected_routes} | Pop: {population or 0} | ({x_coordinate:.1f}, {y_coordinate:.1f})"
                
                gate_lines.append(gate_line)
            
            # Split into multiple fields if too long
            gates_text = "\n".join(gate_lines)
            if len(gates_text) <= 1024:
                embed.add_field(
                    name=f"🗂️ Gates {start_idx + 1}-{end_idx}",
                    value=gates_text,
                    inline=False
                )
            else:
                # Split into multiple fields
                mid_point = len(gate_lines) // 2
                first_half = "\n".join(gate_lines[:mid_point])
                second_half = "\n".join(gate_lines[mid_point:])
                
                embed.add_field(
                    name=f"🗂️ Gates {start_idx + 1}-{start_idx + mid_point}",
                    value=first_half,
                    inline=True
                )
                embed.add_field(
                    name=f"🗂️ Gates {start_idx + mid_point + 1}-{end_idx}",
                    value=second_half,
                    inline=True
                )
            
            # Add navigation info
            if total_pages > 1:
                nav_text = f"Use `/galaxy debug_gates status:{status} page:<number>` to navigate\n"
                nav_text += f"Pages available: 1-{total_pages}"
                embed.add_field(
                    name="🧭 Navigation",
                    value=nav_text,
                    inline=False
                )
            
            embed.set_footer(text=f"Gate connectivity and status as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error displaying gate debug info: {str(e)}")

    @galaxy_group.command(name="debug_dormant_corridors", description="Diagnose dormant corridor accessibility issues")
    async def debug_dormant_corridors(self, interaction: discord.Interaction):
        """Debug dormant corridors that appear on galaxy map but aren't accessible"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            # Get character location for context
            character = self.db.execute_query(
                "SELECT current_location FROM characters WHERE discord_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not character:
                await interaction.followup.send("You need to be a registered character to use this command.", ephemeral=True)
                return
                
            current_location_id = character[0]
            
            # Get location name
            location_info = self.db.execute_query(
                "SELECT name, location_type FROM locations WHERE location_id = %s",
                (current_location_id,),
                fetch='one'
            )
            
            current_location_name = location_info[0] if location_info else "Unknown"
            
            # Check all corridors from current location
            all_corridors = self.db.execute_query(
                """SELECT c.corridor_id, c.name, c.is_active, c.last_shift,
                          l.name as dest_name, l.location_type as dest_type
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   WHERE c.origin_location = %s
                   ORDER BY c.is_active DESC, c.name""",
                (current_location_id,),
                fetch='all'
            )
            
            # Separate active and dormant corridors
            active_corridors = [c for c in all_corridors if c[2] == 1]
            dormant_corridors = [c for c in all_corridors if c[2] == 0]
            
            # Get overall corridor statistics
            total_active = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = true", fetch='one')[0]
            total_dormant = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = false", fetch='one')[0]
            
            embed = discord.Embed(
                title="🔍 Dormant Corridor Diagnostics",
                description=f"**Current Location:** {current_location_name}\n**Location Type:** {location_info[1] if location_info else 'Unknown'}",
                color=0x3498db
            )
            
            # Galaxy-wide statistics
            embed.add_field(
                name="📊 Galaxy Statistics",
                value=f"**Total Active Corridors:** {total_active}\n"
                      f"**Total Dormant Corridors:** {total_dormant}\n"
                      f"**Active/Dormant Ratio:** {total_active/(total_dormant or 1):.2f}",
                inline=False
            )
            
            # Local corridor analysis
            if active_corridors:
                active_list = []
                for c in active_corridors[:5]:  # Limit to first 5
                    shift_info = f" (Shift: {c[3][:10] if c[3] else 'Never'})" if c[3] else ""
                    active_list.append(f"✅ **{c[1]}** → {c[4]}{shift_info}")
                
                if len(active_corridors) > 5:
                    active_list.append(f"... and {len(active_corridors) - 5} more")
                    
                embed.add_field(
                    name=f"🟢 Active Routes from Here ({len(active_corridors)})",
                    value="\n".join(active_list) if active_list else "None",
                    inline=False
                )
            
            if dormant_corridors:
                dormant_list = []
                for c in dormant_corridors[:5]:  # Limit to first 5
                    shift_info = f" (Shift: {c[3][:10] if c[3] else 'Never'})" if c[3] else ""
                    dormant_list.append(f"⭕ **{c[1]}** → {c[4]}{shift_info}")
                
                if len(dormant_corridors) > 5:
                    dormant_list.append(f"... and {len(dormant_corridors) - 5} more")
                    
                embed.add_field(
                    name=f"🌫️ Dormant Routes from Here ({len(dormant_corridors)})",
                    value="\n".join(dormant_list) if dormant_list else "None",
                    inline=False
                )
                
                # Analysis of dormant corridors
                analysis = []
                recent_shift_count = sum(1 for c in dormant_corridors if c[3] and 
                                       (datetime.now() - safe_datetime_parse(c[3])).days < 7)
                                       
                analysis.append(f"**Recent Shifts (7 days):** {recent_shift_count}/{len(dormant_corridors)}")
                
                if dormant_corridors:
                    analysis.append("**Issue:** These dormant corridors are visible but inaccessible in travel menus")
                    analysis.append("**Expected:** When visible, dormant corridors should function like active ones")
                
                embed.add_field(
                    name="🔍 Analysis",
                    value="\n".join(analysis),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🌫️ Dormant Routes from Here",
                    value="No dormant corridors found from this location",
                    inline=False
                )
            
            embed.set_footer(text=f"Diagnostic run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error running dormant corridor diagnostics: {str(e)}")

    @galaxy_group.command(name="activate_dormant_corridors", description="Manually activate dormant corridors for better connectivity")
    @app_commands.describe(
        intensity="How many dormant corridors to activate (1-5, higher = more activations)"
    )
    async def activate_dormant_corridors(self, interaction: discord.Interaction, intensity: int = 2):
        """Manually activate dormant corridors that should be accessible"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
            
        if intensity < 1 or intensity > 5:
            await interaction.response.send_message("Intensity must be between 1 and 5.", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            # Get all dormant corridors (excluding local space routes)
            dormant_corridors = self.db.execute_query(
                """SELECT corridor_id, name, origin_location, destination_location 
                   FROM corridors 
                   WHERE is_active = false
                   AND name NOT LIKE '%Approach%' 
                   AND name NOT LIKE '%Arrival%' 
                   AND name NOT LIKE '%Departure%'
                   AND name NOT LIKE '%Local Space%'""",
                fetch='all'
            )
            
            if not dormant_corridors:
                await interaction.followup.send("No dormant corridors found to activate.")
                return
            
            # Calculate how many to activate based on intensity
            max_activations = len(dormant_corridors) // (6 - intensity)
            actual_activations = min(max_activations, len(dormant_corridors))
            
            if actual_activations == 0:
                actual_activations = min(1, len(dormant_corridors))  # Activate at least 1 if possible
            
            # Randomly select corridors to activate
            corridors_to_activate = random.sample(dormant_corridors, actual_activations)
            
            activated_list = []
            affected_locations = set()
            
            for corridor in corridors_to_activate:
                # Check if activation would improve connectivity
                self.db.execute_query(
                    "UPDATE corridors SET is_active = true WHERE corridor_id = %s",
                    (corridor[0],)
                )
                
                activated_list.append(corridor[1])
                affected_locations.add(corridor[2])
                affected_locations.add(corridor[3])
                print(f"🟢 Manually activated corridor: {corridor[1]}")
            
            # Update last shift timestamp for activated corridors
            corridor_ids = [c[0] for c in corridors_to_activate]
            if corridor_ids:
                self.db.execute_query(
                    "UPDATE corridors SET last_shift = NOW() WHERE corridor_id IN ({})".format(
                        ','.join('%s' * len(corridor_ids))
                    ),
                    corridor_ids
                )
            
            embed = discord.Embed(
                title="🟢 Dormant Corridors Activated",
                description=f"Successfully activated {len(activated_list)} dormant corridors for improved galaxy connectivity.",
                color=0x27ae60
            )
            
            if len(activated_list) <= 10:
                embed.add_field(
                    name="📍 Activated Routes",
                    value="\n".join([f"• {name}" for name in activated_list]),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📍 Activated Routes",
                    value="\n".join([f"• {name}" for name in activated_list[:10]]) + f"\n... and {len(activated_list) - 10} more",
                    inline=False
                )
            
            embed.add_field(
                name="📊 Impact",
                value=f"**Corridors Activated:** {len(activated_list)}\n"
                      f"**Locations Affected:** {len(affected_locations)}\n"
                      f"**Remaining Dormant:** {len(dormant_corridors) - len(activated_list)}",
                inline=False
            )
            
            embed.set_footer(text="These corridors are now accessible in travel menus")
            
            await interaction.followup.send(embed=embed)
            
            # Notify players about the changes
            await self._notify_travelers_of_activations(activated_list, affected_locations)
            
        except Exception as e:
            await interaction.followup.send(f"Error activating dormant corridors: {str(e)}")

    async def _notify_travelers_of_activations(self, activated_corridors: list, affected_locations: set):
        """Notify players about newly activated corridors"""
        if not activated_corridors:
            return
            
        # Find players in affected locations
        travelers = self.db.execute_query(
            f"""SELECT DISTINCT c.discord_id, l.name as location_name
                FROM characters c
                JOIN locations l ON c.current_location = l.location_id
                WHERE c.current_location IN ({','.join(['%s'] * len(affected_locations))})""",
            list(affected_locations),
            fetch='all'
        )
        
        if travelers:
            print(f"🌌 Notified {len(travelers)} travelers about {len(activated_corridors)} newly activated corridors")

    async def _execute_corridor_shifts(self, intensity: int, target_region: str = None, shift_type: str = "mixed") -> Dict:
        """Execute corridor shifts based on intensity - Enhanced with non-blocking operations"""
        import asyncio
        
        # MEMORY LEAK FIX: Monitor database connections
        initial_connections = self.db.get_active_connection_count()
        print(f"🔍 Starting corridor shift - Initial DB connections: {initial_connections}")
        
        results = {
            'activated': 0,
            'deactivated': 0, 
            'new_dormant': 0,
            'destinations_changed': 0,
            'affected_locations': set()
        }
        
        # Get all corridors in a single batch operation
        corridor_queries = [
            ("""SELECT corridor_id, name, origin_location, destination_location, travel_time, fuel_cost, danger_level
                FROM corridors 
                WHERE is_active = true 
                AND name NOT LIKE '%Approach%' 
                AND name NOT LIKE '%Arrival%' 
                AND name NOT LIKE '%Departure%'
                AND name NOT LIKE '%Local Space%'""", 'active'),
            ("""SELECT corridor_id, name, origin_location, destination_location, travel_time, fuel_cost, danger_level
                FROM corridors 
                WHERE is_active = false
                AND name NOT LIKE '%Approach%' 
                AND name NOT LIKE '%Arrival%' 
                AND name NOT LIKE '%Departure%'
                AND name NOT LIKE '%Local Space%'""", 'dormant'),
            ("SELECT COUNT(*) FROM locations", 'count')
        ]
        
        # Execute queries concurrently
        active_corridors, dormant_corridors, total_locations = await self._execute_queries_batch(corridor_queries)
        total_locations = total_locations[0] if total_locations else 0
        
        # Yield control to allow other operations
        await asyncio.sleep(0.02)  # Increased yield time
        
        # Execute different shift types based on selection
        if shift_type in ["mixed", "shuffle"]:
            # NEW FEATURE: Destination shuffling for active corridors
            await self._shuffle_corridor_destinations(active_corridors, intensity, results)
            
            # Additional yield after shuffling to prevent database locks
            await asyncio.sleep(0.02)
        
        batch_operations = []
        
        if shift_type in ["mixed", "routes"]:
            # Calculate balanced changes based on intensity - scale properly for large galaxies
            corridor_pool_factor = min(len(active_corridors), len(dormant_corridors)) // (10 - intensity)
            intensity_multiplier = intensity * (2 + intensity)  # More aggressive scaling: 1->3, 2->8, 3->15, 4->24, 5->35
            base_changes = max(corridor_pool_factor, intensity_multiplier)
            variance = max(1, int(base_changes * 0.3))  # 30% variance, minimum 1
            
            actual_deactivations = random.randint(
                max(1, base_changes - variance), 
                min(base_changes + variance, len(active_corridors))
            )
            actual_activations = random.randint(
                max(1, base_changes - variance), 
                min(base_changes + variance, len(dormant_corridors))
            )
            
            # Smart Corridor Redistribution: Conservation-based entropy shifts
            redistribution_pairs = await self._calculate_smart_redistribution(
                active_corridors, dormant_corridors, actual_deactivations, actual_activations
            )
            
            # 3% chance of regional isolation during shifts
            isolated_regions = []
            if random.random() < 0.03 and intensity >= 3:  # Only at higher intensities
                isolated_regions = await self._apply_regional_isolation()
            
            # Build redistribution batch operations
            for deactivate_corridor, activate_corridor in redistribution_pairs:
                # Deactivate old corridor
                if not self._would_isolate_location(deactivate_corridor[0], deactivate_corridor[2], deactivate_corridor[3]):
                    batch_operations.append(
                        ("UPDATE corridors SET is_active = false, last_shift = NOW() WHERE corridor_id = %s", 
                         (deactivate_corridor[0],), 'deactivate', deactivate_corridor)
                    )
                    
                    # Activate replacement corridor if available
                    if activate_corridor:
                        batch_operations.append(
                            ("UPDATE corridors SET is_active = true, last_shift = NOW() WHERE corridor_id = %s", 
                             (activate_corridor[0],), 'activate', activate_corridor)
                        )
            
            # Yield control to prevent database locks during preparation
            await asyncio.sleep(0.02)
        
        # Execute all updates in batches to prevent blocking
        await self._execute_corridor_updates_batch(batch_operations, results, intensity)
        
        # Handle dormant corridor replenishment based on shift type
        if shift_type in ["mixed", "new"]:
            current_dormant_count = len(dormant_corridors) - results['activated']
            target_threshold = total_locations * 2 if shift_type == "mixed" else total_locations
            
            if current_dormant_count < target_threshold:
                base_replenish = max(0, (total_locations - current_dormant_count) // 4)
                if shift_type == "new":
                    # For "new" type, create more dormant corridors
                    replenish_amount = min(intensity * 2, base_replenish * 2)
                else:
                    # For "mixed" type, use normal amount
                    replenish_amount = min(intensity, base_replenish)
                
                if replenish_amount > 0:
                    await self._replenish_dormant_corridors(replenish_amount)
                    results['new_dormant'] = replenish_amount
        
        # MEMORY LEAK FIX: Clear affected_locations set to release references
        if 'affected_locations' in results:
            # Convert set to count for return value before clearing
            affected_count = len(results['affected_locations'])
            results['affected_locations'].clear()  # Clear the set to free memory
            results['affected_locations_count'] = affected_count  # Store count instead
        
        # MEMORY LEAK FIX: Monitor database connections after completion
        final_connections = self.db.get_active_connection_count()
        total_elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"🔍 Corridor shift complete - Final DB connections: {final_connections} - Total time: {total_elapsed:.1f}s")
        if final_connections > initial_connections:
            print(f"⚠️ WARNING: Database connection leak detected! Increased by {final_connections - initial_connections}")
        
        print(f"🌌 Corridor shift results: +{results['activated']} -{results['deactivated']} ~{results['destinations_changed']} new:{results['new_dormant']}")
        
        # Execute the same 4-step post-shift cleanup sequence as manual admin commands
        # This ensures automatic shifts follow the exact same validation rules as manual ones
        print("🔧 Starting post-shift cleanup sequence (following manual command order)...")
        
        # Step 1: Fix routes (approach/arrival/departure routes) - matches /galaxy fix_routes
        try:
            print("🔧 Step 1/4: Fixing routes...")
            route_fixes = await self._execute_fix_routes_logic()
            
            # Force database sync after route fixes
            await asyncio.sleep(0.05)  # Small delay to ensure WAL completion
            
            if route_fixes['total_fixed'] > 0:
                print(f"   ✅ Fixed {route_fixes['total_fixed']} route issues")
                results['route_fixes'] = route_fixes['total_fixed']
            else:
                print("   ✅ All routes validated")
        except Exception as e:
            print(f"   ⚠️ Step 1 failed: {e}")
        
        # Step 2: Fix corridor types - matches /galaxy fix_corridor_types  
        try:
            print("🔧 Step 2/4: Fixing corridor types...")
            
            # Get corridor type counts before classification 
            before_counts = self.db.execute_query("""
                SELECT corridor_type, COUNT(*) as count
                FROM corridors 
                GROUP BY corridor_type
            """, fetch='all')
            
            self.db._classify_existing_corridors()
            
            # Force database sync after classification
            await asyncio.sleep(0.05)  # Ensure classification completes
            
            # Get corridor type counts after classification to show changes
            after_counts = self.db.execute_query("""
                SELECT corridor_type, COUNT(*) as count
                FROM corridors 
                GROUP BY corridor_type
            """, fetch='all')
            
            # Calculate and log changes
            before_dict = {ct: count for ct, count in before_counts}
            after_dict = {ct: count for ct, count in after_counts}
            
            changes = []
            for corridor_type in ['local_space', 'gated', 'ungated']:
                before = before_dict.get(corridor_type, 0)
                after = after_dict.get(corridor_type, 0)
                if before != after:
                    changes.append(f"{corridor_type}: {before}→{after}")
            
            if changes:
                print(f"   ✅ Corridor types corrected: {', '.join(changes)}")
                results['type_corrections'] = len(changes)
            else:
                print("   ✅ All corridor types already correctly classified")
        except Exception as e:
            print(f"   ⚠️ Step 2 failed: {e}")
        
        # Step 3: Fix gate architecture - matches /galaxy fix_gate_architecture
        try:
            print("🔧 Step 3/4: Fixing gate architecture...")
            from utils.architecture_validator import ArchitectureValidator
            validator = ArchitectureValidator(self.db)
            fixes = await validator.validate_and_fix_architecture(silent=True)
            
            # Force database sync after architecture fixes
            await asyncio.sleep(0.05)  # Ensure architecture fixes complete
            
            total_fixes = sum(fixes.values())
            if total_fixes > 0:
                print(f"   ✅ Applied {total_fixes} architecture fixes")
                results['architecture_fixes'] = total_fixes
            else:
                print("   ✅ No architecture violations found")
        except Exception as e:
            print(f"   ⚠️ Step 3 failed: {e}")
        
        # Step 4: Fix long routes - matches /create fix_long_routes
        try:
            print("🔧 Step 4/4: Fixing long routes...")
            creation_cog = self.bot.get_cog('CreationCog')
            if creation_cog:
                long_route_fixes = await creation_cog._execute_fix_long_routes_logic()
                if long_route_fixes and long_route_fixes.get('routes_fixed', 0) > 0:
                    print(f"   ✅ Fixed {long_route_fixes['routes_fixed']} long routes")
                    results['long_route_fixes'] = long_route_fixes['routes_fixed']
                else:
                    print("   ✅ All route times validated")
            else:
                # Fallback to internal long route fix if CreationCog not available
                long_route_results = await self._fix_overly_long_routes()
                if long_route_results['routes_fixed'] > 0:
                    print(f"   ✅ Fixed {long_route_results['routes_fixed']} long routes (fallback)")
                    results['long_route_fixes'] = long_route_results['routes_fixed']
                else:
                    print("   ✅ All route times validated (fallback)")
                    
            # Final database sync to ensure all changes are committed
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"   ⚠️ Step 4 failed: {e}")
        
        # Log cleanup summary
        cleanup_summary = []
        if results.get('route_fixes', 0) > 0:
            cleanup_summary.append(f"{results['route_fixes']} routes fixed")
        if results.get('type_corrections', 0) > 0:
            cleanup_summary.append(f"{results['type_corrections']} type corrections")
        if results.get('architecture_fixes', 0) > 0:
            cleanup_summary.append(f"{results['architecture_fixes']} architecture fixes")
        if results.get('long_route_fixes', 0) > 0:
            cleanup_summary.append(f"{results['long_route_fixes']} long route fixes")
        
        if cleanup_summary:
            print(f"✅ Post-shift cleanup complete: {', '.join(cleanup_summary)}")
        else:
            print("✅ Post-shift cleanup complete - no fixes needed, all rules already followed!")
        
        return results
    
    async def _execute_queries_batch(self, queries: list) -> tuple:
        """Execute multiple queries in batch to reduce database lock time"""
        import asyncio
        
        results = []
        for i, (query, query_type) in enumerate(queries):
            # Yield control between EVERY query to prevent blocking
            await asyncio.sleep(0.01)  # Increased from 0.001 to give more time
            
            try:
                result = self.db.execute_query(query, fetch='all' if query_type != 'count' else 'one')
                results.append(result)
                
                # Extra yield after database-intensive queries
                if query_type == 'active' or query_type == 'dormant':
                    await asyncio.sleep(0.02)
                    
            except Exception as e:
                print(f"⚠️ Query failed in batch: {e}")
                results.append([] if query_type != 'count' else [0])
                await asyncio.sleep(0.05)  # Wait longer on errors
        
        return tuple(results)
    
    async def _execute_corridor_updates_batch(self, operations: list, results: dict, intensity: int):
        """Execute corridor updates in small batches to prevent database hangs"""
        import asyncio
        
        batch_size = 3  # REDUCED: Process only 3 corridors at a time to prevent locks
        
        for i in range(0, len(operations), batch_size):
            batch = operations[i:i + batch_size]
            
            # Process each operation individually with frequent yielding
            for j, (query, params, operation_type, corridor) in enumerate(batch):
                try:
                    # Execute query with quick commit to release database lock
                    self.db.execute_query(query, params)
                    
                    if operation_type == 'deactivate':
                        results['deactivated'] += 1
                        # MEMORY LEAK FIX: Limit set size to prevent unbounded growth
                        if len(results['affected_locations']) < 1000:  # Maximum 1000 locations
                            results['affected_locations'].add(corridor[2])
                            results['affected_locations'].add(corridor[3])
                        print(f"🔴 Deactivated corridor: {corridor[1]}")
                    elif operation_type == 'activate':
                        results['activated'] += 1
                        # MEMORY LEAK FIX: Limit set size to prevent unbounded growth
                        if len(results['affected_locations']) < 1000:  # Maximum 1000 locations
                            results['affected_locations'].add(corridor[2])
                            results['affected_locations'].add(corridor[3])
                        print(f"🟢 Activated corridor: {corridor[1]}")
                    
                    # Yield after EVERY single database operation
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    print(f"⚠️ Error updating corridor {corridor[1]}: {e}")
                    await asyncio.sleep(0.02)  # Wait longer on database errors
            
            # Additional yield after each batch to ensure other bot operations can run
            await asyncio.sleep(0.02)
        
        # Simulate gate movements for gates affected by corridor shifts
        affected_gates = set()
        for _, _, operation_type, corridor in operations:
            # Add both endpoints of deactivated corridors
            origin_loc = self.db.execute_query(
                "SELECT location_type FROM locations WHERE location_id = %s", 
                (corridor[2],), fetch='one'
            )
            dest_loc = self.db.execute_query(
                "SELECT location_type FROM locations WHERE location_id = %s", 
                (corridor[3],), fetch='one'
            )
            
            if origin_loc and origin_loc[0] == 'gate':
                affected_gates.add(corridor[2])
            if dest_loc and dest_loc[0] == 'gate':
                affected_gates.add(corridor[3])
        
        if affected_gates:
            gate_results = await self._simulate_gate_movements_for_affected(list(affected_gates), intensity)
            print(f"🚪 Gate movements: {gate_results['gates_abandoned']} gates affected by corridor shifts")
        
        # MEMORY LEAK FIX: Explicit cleanup after batch operations
        del operations  # Clear the operations list to free memory
        affected_gates.clear()  # Clear the set to free memory
        
        return results

    async def _shuffle_corridor_destinations(self, active_corridors: list, intensity: int, results: dict):
        """
        Shuffle corridor destinations to completely change the galaxy's route system.
        This is the core enhancement - corridors stay active but lead to different places!
        """
        import asyncio
        import time
        
        if not active_corridors:
            return
        
        
        # Progress tracking for large operations
        start_time = time.time()
        
        # Calculate how many corridors to shuffle based on intensity - reduced for better gameplay
        total_corridors = len(active_corridors)
        shuffle_percentage = 0.05 + (intensity * 0.08)  # 5% to 45% based on intensity 1-5 (much lower)
        corridors_to_shuffle = int(total_corridors * shuffle_percentage)
        
        # Ensure minimum of 1 and don't exceed available corridors
        corridors_to_shuffle = max(1, min(corridors_to_shuffle, total_corridors))
        
        print(f"🔀 Shuffling destinations for {corridors_to_shuffle}/{total_corridors} corridors (intensity {intensity})")
        
        # Get all possible destinations (excluding local space connections)
        try:
            all_destinations = self.db.execute_query(
                """SELECT location_id, name, location_type, x_coordinate, y_coordinate 
                   FROM locations 
                   WHERE location_type IN ('colony', 'space_station', 'outpost', 'gate')
                   ORDER BY location_id""",
                fetch='all'
            )
            print(f"🎯 Loaded {len(all_destinations)} destinations for shuffling")
        except Exception as e:
            print(f"❌ Failed to fetch destinations: {e}")
            return
        
        # Yield control
        await asyncio.sleep(0.01)
        
        if len(all_destinations) < 2:
            print("⚠️ Not enough destinations for shuffling")
            return
            
        # Select random corridors to shuffle
        corridors_to_shuffle_list = random.sample(active_corridors, corridors_to_shuffle)
        
        # OPTIMIZATION: Pre-fetch ALL origin location data in one bulk query
        origin_ids = [corridor[2] for corridor in corridors_to_shuffle_list]  # corridor[2] is origin_location
        origin_ids_str = ','.join(map(str, origin_ids))
        
        origin_data = {}
        try:
            origin_locations = self.db.execute_query(
                f"""SELECT location_id, x_coordinate, y_coordinate, system_name, location_type 
                   FROM locations 
                   WHERE location_id IN ({origin_ids_str})""",
                fetch='all'
            )
            for loc_id, x, y, system, location_type in origin_locations:
                origin_data[loc_id] = {'x': x, 'y': y, 'system': system, 'type': location_type}
            print(f"⚡ Pre-loaded {len(origin_data)} origin locations for fast processing")
        except Exception as e:
            print(f"❌ Bulk origin fetch failed: {e}")
            return
        
        # Prepare batch operations for corridor updates
        shuffle_operations = []
        
        # OPTIMIZATION: Get all destination systems in one bulk query
        dest_ids = [dest[0] for dest in all_destinations]
        dest_ids_str = ','.join(map(str, dest_ids))
        
        destination_systems = {}
        try:
            dest_system_data = self.db.execute_query(
                f"""SELECT location_id, system_name 
                   FROM locations 
                   WHERE location_id IN ({dest_ids_str})""",
                fetch='all'
            )
            for loc_id, system in dest_system_data:
                destination_systems[loc_id] = system
            print(f"🗺️ Organized {len(destination_systems)} destinations by system for fast lookups")
        except Exception as e:
            print(f"❌ Destination systems fetch failed: {e}")
            return
        
        # Pre-organize destinations by system for O(1) lookups
        destination_by_system = {}
        location_data = {}
        for dest_id, dest_name, dest_type, dest_x, dest_y in all_destinations:
            location_data[dest_id] = {
                'name': dest_name,
                'type': dest_type,
                'x': dest_x,
                'y': dest_y
            }
            
            system_name = destination_systems.get(dest_id)
            if system_name:
                if system_name not in destination_by_system:
                    destination_by_system[system_name] = []
                destination_by_system[system_name].append((dest_id, dest_name, dest_type, dest_x, dest_y))
        
        # Process corridors in micro-batches with aggressive yielding for large operations
        batch_size = 1  # Process just 1 corridor at a time for maximum non-blocking
        processed_count = 0
        
        for i in range(0, len(corridors_to_shuffle_list), batch_size):
            batch = corridors_to_shuffle_list[i:i + batch_size]
            
            # Progress reporting every 50 corridors for large operations
            if processed_count % 50 == 0 and processed_count > 0:
                progress_pct = (processed_count / len(corridors_to_shuffle_list)) * 100
                elapsed = time.time() - start_time
                rate = processed_count / elapsed if elapsed > 0 else 0
                eta = (len(corridors_to_shuffle_list) - processed_count) / rate if rate > 0 else 0
                print(f"🔀 Shuffle progress: {processed_count}/{len(corridors_to_shuffle_list)} ({progress_pct:.1f}%) - {rate:.1f}/sec - ETA: {eta:.0f}s")
            
            for corridor in batch:
                corridor_id, name, origin_id, old_dest_id, travel_time, fuel_cost, danger_level = corridor
                
                # OPTIMIZATION: Use pre-fetched origin data instead of querying
                origin_info = origin_data.get(origin_id)
                if not origin_info:
                    processed_count += 1
                    continue
                
                origin_x, origin_y, origin_system, origin_type = origin_info['x'], origin_info['y'], origin_info['system'], origin_info['type']
                
                # OPTIMIZATION: Use pre-organized destinations by system for faster lookups
                valid_destinations = []
                for system_name, destinations in destination_by_system.items():
                    if system_name != origin_system:  # Different system
                        for dest_id, dest_name, dest_type, dest_x, dest_y in destinations:
                            if dest_id != origin_id and dest_id != old_dest_id:
                                valid_destinations.append((dest_id, dest_name, dest_type, dest_x, dest_y))
                
                if not valid_destinations:
                    processed_count += 1
                    continue
                
                # Filter destinations based on origin type to maintain proper gate logic
                if origin_type == 'gate':
                    # Gates should heavily prioritize connecting to other gates (gated corridors)
                    gate_destinations = [dest for dest in valid_destinations if dest[2] == 'gate']
                    
                    # 85% chance to connect to another gate if available, 15% chance for ungated connection
                    if gate_destinations and random.random() < 0.85:
                        valid_destinations = gate_destinations
                    else:
                        # Rare ungated connection - remove other gates to avoid gate-to-gate ungated
                        valid_destinations = [dest for dest in valid_destinations if dest[2] != 'gate']
                
                elif origin_type in ['colony', 'space_station', 'outpost']:
                    # Non-gate locations should rarely connect to gates via ungated corridors
                    gate_destinations = [dest for dest in valid_destinations if dest[2] == 'gate']
                    non_gate_destinations = [dest for dest in valid_destinations if dest[2] != 'gate']
                    
                    # Only 10% chance for major locations to connect to gates ungated, 90% to other major locations
                    if gate_destinations and non_gate_destinations and random.random() < 0.10:
                        valid_destinations = gate_destinations
                    elif non_gate_destinations:
                        valid_destinations = non_gate_destinations
                
                if not valid_destinations:
                    processed_count += 1
                    continue
                
                # Pick new destination and calculate parameters
                new_dest_id, new_dest_name, new_dest_type, new_dest_x, new_dest_y = random.choice(valid_destinations)
                distance = ((new_dest_x - origin_x) ** 2 + (new_dest_y - origin_y) ** 2) ** 0.5
                
                # Adjust travel time and fuel cost based on new distance
                new_travel_time = max(180, int(200 + distance * 15))  # Minimum 3 minutes
                new_fuel_cost = max(10, int(15 + distance * 2))
                
                # Slightly randomize danger level
                new_danger_level = max(1, min(5, danger_level + random.randint(-1, 1)))
                
                # Determine correct corridor type for new connection
                new_corridor_type = self._determine_corridor_type(origin_id, new_dest_id, name)
                
                # Add to shuffle operations batch
                shuffle_operations.append({
                    'corridor_id': corridor_id,
                    'name': name,
                    'new_dest_id': new_dest_id,
                    'new_dest_name': new_dest_name,
                    'new_travel_time': new_travel_time,
                    'new_fuel_cost': new_fuel_cost,
                    'new_danger_level': new_danger_level,
                    'new_corridor_type': new_corridor_type,
                    'origin_id': origin_id,
                    'old_dest_id': old_dest_id
                })
                
                processed_count += 1
            
            # Smart yielding - only yield every 10 corridors to reduce overhead
            if processed_count % 10 == 0:
                await asyncio.sleep(0.001)  # Minimal yield for responsiveness
        
        # Execute all shuffle operations in batches
        await self._execute_shuffle_operations_batch(shuffle_operations, results)
    
    async def _execute_shuffle_operations_batch(self, operations: list, results: dict):
        """Execute corridor destination shuffles in batches to prevent database hangs"""
        import asyncio
        
        batch_size = 50  # OPTIMIZATION: Process 50 operations at a time for better performance
        operation_count = 0
        
        for i in range(0, len(operations), batch_size):
            batch = operations[i:i + batch_size]
            
            # Progress reporting for large shuffle operations
            if operation_count % 100 == 0 and operation_count > 0:
                progress_pct = (operation_count / len(operations)) * 100
                print(f"📝 Executing shuffle operations: {operation_count}/{len(operations)} ({progress_pct:.1f}%)")
            
            for op in batch:
                try:
                    # Update the corridor with new destination, parameters, and correct corridor type
                    self.db.execute_query(
                        """UPDATE corridors 
                           SET destination_location = %s, travel_time = %s, fuel_cost = %s, danger_level = %s, corridor_type = %s, last_shift = NOW()
                           WHERE corridor_id = %s""",
                        (op['new_dest_id'], op['new_travel_time'], op['new_fuel_cost'], 
                         op['new_danger_level'], op['new_corridor_type'], op['corridor_id'])
                    )
                    
                    # Yield after main update to prevent blocking
                    await asyncio.sleep(0.01)
                    
                    # Check for bidirectional corridors
                    is_bidirectional = self.db.execute_query(
                        "SELECT is_bidirectional FROM corridors WHERE corridor_id = %s",
                        (op['corridor_id'],), fetch='one'
                    )
                    
                    # Yield after query
                    await asyncio.sleep(0.005)
                    
                    if is_bidirectional and is_bidirectional[0]:
                        # Find the reverse corridor and update it too
                        reverse_corridor = self.db.execute_query(
                            """SELECT corridor_id FROM corridors 
                               WHERE origin_location = %s AND destination_location = %s AND corridor_id != %s""",
                            (op['old_dest_id'], op['origin_id'], op['corridor_id']), fetch='one'
                        )
                        
                        # Yield after query
                        await asyncio.sleep(0.005)
                        
                        if reverse_corridor:
                            # Determine corridor type for reverse direction 
                            reverse_corridor_type = self._determine_corridor_type(op['new_dest_id'], op['origin_id'], op['name'])
                            
                            self.db.execute_query(
                                """UPDATE corridors 
                                   SET origin_location = %s, travel_time = %s, fuel_cost = %s, danger_level = %s, corridor_type = %s, last_shift = NOW()
                                   WHERE corridor_id = %s""",
                                (op['new_dest_id'], op['new_travel_time'], op['new_fuel_cost'], 
                                 op['new_danger_level'], reverse_corridor_type, reverse_corridor[0])
                            )
                            
                            # Yield after reverse update
                            await asyncio.sleep(0.01)
                    
                    # Track the change
                    results['destinations_changed'] += 1
                    # MEMORY LEAK FIX: Limit set size to prevent unbounded growth
                    if len(results['affected_locations']) < 1000:  # Maximum 1000 locations
                        results['affected_locations'].add(op['origin_id'])
                        results['affected_locations'].add(op['old_dest_id'])
                        results['affected_locations'].add(op['new_dest_id'])
                    
                    # Detailed logging for large operations (reduced frequency)
                    if operation_count % 200 == 0:
                        print(f"🔀 Shuffled {op['name']}: -> {op['new_dest_name']}")
                    
                    operation_count += 1
                    
                except Exception as e:
                    print(f"⚠️ Error shuffling corridor {op['name']}: {e}")
                    operation_count += 1
                    await asyncio.sleep(0.02)  # Wait longer on errors
            
            # Yield control after each batch to prevent blocking
            await asyncio.sleep(0.01)  # Yield after batch for responsiveness
        
        elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
        rate = len(operations) / elapsed_time if elapsed_time > 0 else 0
        print(f"✅ Destination shuffle complete: {results['destinations_changed']} corridors redirected in {elapsed_time:.1f}s ({rate:.1f}/sec)")
        
        # MEMORY LEAK FIX: Explicit cleanup after shuffle operations
        del operations  # Clear the operations list to free memory

    def _would_isolate_location(self, corridor_id: int, origin_id: int, dest_id: int) -> bool:
        """Check if deactivating a corridor would completely isolate a location or break gate connectivity"""
        
        # Count active connections for both endpoints
        origin_connections = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE (origin_location = %s OR destination_location = %s) AND is_active = true AND corridor_id != %s",
            (origin_id, origin_id, corridor_id),
            fetch='one'
        )[0]
        
        dest_connections = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE (origin_location = %s OR destination_location = %s) AND is_active = true AND corridor_id != %s",
            (dest_id, dest_id, corridor_id),
            fetch='one'
        )[0]
        
        # Don't allow complete isolation
        if origin_connections <= 1 or dest_connections <= 1:
            return True
            
        # Special protection for gates - check if either endpoint is a gate
        gate_info = self.db.execute_query(
            "SELECT location_id, location_type, gate_status FROM locations WHERE location_id IN (%s, %s)",
            (origin_id, dest_id),
            fetch='all'
        )
        
        for location_id, location_type, gate_status in gate_info:
            if location_type == 'gate' and gate_status == 'active':
                # Check if this gate would lose all gated corridors (inter-system routes)
                remaining_gated = self.db.execute_query(
                    """SELECT COUNT(*) FROM corridors c
                       JOIN locations lo ON c.origin_location = lo.location_id
                       JOIN locations ld ON c.destination_location = ld.location_id
                       WHERE (c.origin_location = %s OR c.destination_location = %s)
                       AND c.is_active = true AND c.corridor_id != %s
                       AND c.corridor_type = 'gated'
                       AND lo.system_name != ld.system_name""",
                    (location_id, location_id, corridor_id),
                    fetch='one'
                )[0]
                
                # Protect gates that would lose their last gated route
                if remaining_gated == 0:
                    return True
                    
        return False

    async def _calculate_smart_redistribution(self, active_corridors, dormant_corridors, target_deactivations, target_activations):
        """Calculate conservation-based corridor redistribution pairs to maintain connectivity"""
        
        redistribution_pairs = []
        used_dormant = set()
        
        # Separate gated and ungated corridors for smart pairing
        active_gated = [c for c in active_corridors if self._is_gated_corridor(c[0])]
        active_ungated = [c for c in active_corridors if not self._is_gated_corridor(c[0])]
        dormant_gated = [c for c in dormant_corridors if self._is_gated_corridor(c[0])]
        dormant_ungated = [c for c in dormant_corridors if not self._is_gated_corridor(c[0])]
        
        print(f"🔄 Smart redistribution: {len(active_gated)} active gated, {len(dormant_gated)} dormant gated available")
        
        deactivations_made = 0
        max_attempts = target_deactivations * 3  # More attempts than needed
        
        for attempt in range(max_attempts):
            if deactivations_made >= target_deactivations:
                break
                
            # Choose corridor to deactivate (prefer gated for better redistribution)
            if active_gated and random.random() < 0.7:  # 70% chance to pick gated
                corridor_to_deactivate = random.choice(active_gated)
                active_gated.remove(corridor_to_deactivate)
                replacement_pool = dormant_gated
            else:
                if active_ungated:
                    corridor_to_deactivate = random.choice(active_ungated)
                    active_ungated.remove(corridor_to_deactivate)
                    replacement_pool = dormant_ungated
                else:
                    continue
            
            # Find smart replacement: prioritize maintaining connectivity for same gates
            corridor_id, name, origin_id, dest_id = corridor_to_deactivate[:4]
            replacement_corridor = None
            
            # Look for replacement that maintains connectivity for either endpoint
            for candidate in replacement_pool:
                cand_id, cand_name, cand_origin, cand_dest = candidate[:4]
                if cand_id in used_dormant:
                    continue
                    
                # Prefer corridors that maintain connectivity for same gates
                if cand_origin == origin_id or cand_dest == dest_id or cand_origin == dest_id or cand_dest == origin_id:
                    replacement_corridor = candidate
                    break
            
            # If no perfect match, pick any available replacement
            if not replacement_corridor:
                available_candidates = [c for c in replacement_pool if c[0] not in used_dormant]
                if available_candidates:
                    replacement_corridor = random.choice(available_candidates)
            
            # Create redistribution pair
            if replacement_corridor:
                used_dormant.add(replacement_corridor[0])
                replacement_pool = [c for c in replacement_pool if c[0] != replacement_corridor[0]]
            
            redistribution_pairs.append((corridor_to_deactivate, replacement_corridor))
            deactivations_made += 1
        
        print(f"🔄 Created {len(redistribution_pairs)} redistribution pairs ({deactivations_made} corridors to shift)")
        return redistribution_pairs

    async def _apply_regional_isolation(self):
        """Apply 3% chance regional isolation by cutting external corridors from random systems"""
        
        # Get all systems with gates
        systems_with_gates = self.db.execute_query(
            """SELECT DISTINCT system_name, COUNT(*) as gate_count 
               FROM locations 
               WHERE location_type = 'gate' AND system_name IS NOT NULL 
               GROUP BY system_name 
               HAVING gate_count > 0""",
            fetch='all'
        )
        
        if not systems_with_gates:
            return []
        
        # Pick 1-2 systems to isolate (small chance, big impact)
        num_to_isolate = min(2, max(1, len(systems_with_gates) // 20))  # ~5% of systems max
        systems_to_isolate = random.sample(systems_with_gates, num_to_isolate)
        
        isolated_regions = []
        
        for system_name, gate_count in systems_to_isolate:
            # Get all gates in this system
            system_gates = self.db.execute_query(
                "SELECT location_id FROM locations WHERE system_name = %s AND location_type = 'gate'",
                (system_name,),
                fetch='all'
            )
            
            if not system_gates:
                continue
            
            gate_ids = [gate[0] for gate in system_gates]
            
            # Deactivate ALL external corridors from this system (cross-system gated routes)
            external_corridors_deactivated = 0
            for gate_id in gate_ids:
                # Find and deactivate gated corridors to other systems
                external_corridors = self.db.execute_query(
                    """SELECT c.corridor_id FROM corridors c
                       JOIN locations lo ON c.origin_location = lo.location_id
                       JOIN locations ld ON c.destination_location = ld.location_id
                       WHERE (c.origin_location = %s OR c.destination_location = %s)
                       AND c.corridor_type = 'gated' 
                       AND c.is_active = true
                       AND lo.system_name != ld.system_name""",
                    (gate_id, gate_id),
                    fetch='all'
                )
                
                for (corridor_id,) in external_corridors:
                    self.db.execute_query(
                        "UPDATE corridors SET is_active = false, last_shift = NOW() WHERE corridor_id = %s",
                        (corridor_id,)
                    )
                    external_corridors_deactivated += 1
            
            if external_corridors_deactivated > 0:
                isolated_regions.append(system_name)
                print(f"🌀 REGIONAL ISOLATION: {system_name} system cut off from galaxy ({external_corridors_deactivated} external routes severed)")
        
        return isolated_regions

    def _is_gated_corridor(self, corridor_id):
        """Check if a corridor is a gated corridor (gate-to-gate, cross-system)"""
        corridor_info = self.db.execute_query(
            """SELECT c.corridor_type, lo.location_type as origin_type, ld.location_type as dest_type,
                      lo.system_name as origin_system, ld.system_name as dest_system
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE c.corridor_id = %s""",
            (corridor_id,),
            fetch='one'
        )
        
        if not corridor_info:
            return False
            
        corridor_type, origin_type, dest_type, origin_system, dest_system = corridor_info
        
        # Gated corridors: gate-to-gate, cross-system, or explicitly marked as gated
        return (corridor_type == 'gated' or 
                (origin_type == 'gate' and dest_type == 'gate' and origin_system != dest_system))

    async def _validate_and_repair_gate_connectivity(self) -> Dict:
        """Validate gate connectivity and repair isolated gates by activating dormant corridors"""
        
        repair_results = {
            'gates_repaired': 0,
            'corridors_activated': 0,
            'gates_checked': 0
        }
        
        # Find all active gates and check their gated corridor connections
        isolated_gates = self.db.execute_query(
            """SELECT g.location_id, g.name, g.system_name,
                      COUNT(CASE WHEN c.corridor_type = 'gated' AND c.is_active = true 
                                 AND lo.system_name != ld.system_name THEN 1 END) as gated_routes
               FROM locations g
               LEFT JOIN corridors c ON (c.origin_location = g.location_id OR c.destination_location = g.location_id)
               LEFT JOIN locations lo ON c.origin_location = lo.location_id
               LEFT JOIN locations ld ON c.destination_location = ld.location_id
               WHERE g.location_type = 'gate' AND g.gate_status = 'active'
               GROUP BY g.location_id, g.name, g.system_name
               HAVING gated_routes = 0""",
            fetch='all'
        )
        
        repair_results['gates_checked'] = len(isolated_gates)
        
        for gate_id, gate_name, gate_system, gated_routes in isolated_gates:
            # Find dormant gated corridors connected to this gate
            dormant_gated = self.db.execute_query(
                """SELECT c.corridor_id, c.name, c.origin_location, c.destination_location
                   FROM corridors c
                   JOIN locations lo ON c.origin_location = lo.location_id
                   JOIN locations ld ON c.destination_location = ld.location_id
                   WHERE (c.origin_location = %s OR c.destination_location = %s)
                   AND c.is_active = false
                   AND c.corridor_type = 'gated'
                   AND lo.system_name != ld.system_name
                   LIMIT 2""",  # Activate up to 2 gated routes per isolated gate
                (gate_id, gate_id),
                fetch='all'
            )
            
            if dormant_gated:
                for corridor_id, corridor_name, origin_id, dest_id in dormant_gated:
                    # Activate the dormant gated corridor
                    self.db.execute_query(
                        "UPDATE corridors SET is_active = true, last_shift = NOW() WHERE corridor_id = %s",
                        (corridor_id,)
                    )
                    repair_results['corridors_activated'] += 1
                
                repair_results['gates_repaired'] += 1
                print(f"🔧 Repaired isolated gate: {gate_name} - activated {len(dormant_gated)} gated routes")
        
        return repair_results

    async def _validate_routing_complexity(self) -> Dict:
        """Validate that routing remains complex after shifts and break overly direct routes"""
        
        complexity_results = {
            'routes_broken': 0,
            'paths_analyzed': 0
        }
        
        # Sample some distant location pairs to check for overly direct routes
        all_major_locations = self.db.execute_query(
            "SELECT location_id, name, x_coordinate, y_coordinate, system_name FROM locations WHERE location_type IN ('colony', 'space_station', 'outpost')",
            fetch='all'
        )
        
        if len(all_major_locations) < 4:
            return complexity_results
        
        # Test routing complexity for random distant pairs
        test_pairs = min(10, len(all_major_locations) // 5)  # Test 10 pairs or 20% of locations
        sampled_pairs = []
        
        for _ in range(test_pairs * 3):  # More attempts to find good test pairs
            if len(sampled_pairs) >= test_pairs:
                break
                
            loc_a, loc_b = random.sample(all_major_locations, 2)
            loc_a_id, loc_a_name, loc_a_x, loc_a_y, loc_a_system = loc_a
            loc_b_id, loc_b_name, loc_b_x, loc_b_y, loc_b_system = loc_b
            
            # Only test cross-system pairs (should require multiple hops)
            if loc_a_system == loc_b_system:
                continue
                
            # Only test reasonably distant pairs
            distance = math.sqrt((loc_a_x - loc_b_x) ** 2 + (loc_a_y - loc_b_y) ** 2)
            if distance < 50:  # Too close
                continue
                
            sampled_pairs.append((loc_a, loc_b, distance))
        
        # Analyze routing complexity for each pair
        for loc_a, loc_b, distance in sampled_pairs:
            loc_a_id, loc_a_name, loc_a_x, loc_a_y, loc_a_system = loc_a
            loc_b_id, loc_b_name, loc_b_x, loc_b_y, loc_b_system = loc_b
            
            complexity_results['paths_analyzed'] += 1
            
            # Check if there are any ungated corridors that make this too direct
            direct_ungated = self.db.execute_query(
                """SELECT c.corridor_id FROM corridors c
                   WHERE ((c.origin_location = %s AND c.destination_location = %s) OR
                          (c.origin_location = %s AND c.destination_location = %s))
                   AND c.corridor_type = 'ungated' 
                   AND c.is_active = true""",
                (loc_a_id, loc_b_id, loc_b_id, loc_a_id),
                fetch='all'
            )
            
            # If there's a direct ungated route over long distance, consider breaking it (entropy)
            if direct_ungated and distance > 80:
                for (corridor_id,) in direct_ungated:
                    if random.random() < 0.4:  # 40% chance to break overly direct long routes
                        self.db.execute_query(
                            "UPDATE corridors SET is_active = false, last_shift = NOW() WHERE corridor_id = %s",
                            (corridor_id,)
                        )
                        complexity_results['routes_broken'] += 1
            
            # Check for too many parallel gated routes between same systems
            if distance > 100:  # Only for very distant locations
                # Count active gated routes between these systems
                parallel_gated = self.db.execute_query(
                    """SELECT COUNT(*) FROM corridors c
                       JOIN locations lo ON c.origin_location = lo.location_id
                       JOIN locations ld ON c.destination_location = ld.location_id
                       WHERE lo.system_name = %s AND ld.system_name = %s
                       AND c.corridor_type = 'gated' AND c.is_active = true""",
                    (loc_a_system, loc_b_system),
                    fetch='one'
                )[0]
                
                # If too many parallel routes, deactivate some (entropy effect)
                if parallel_gated > 3:  # More than 3 parallel gated routes
                    excess_routes = self.db.execute_query(
                        """SELECT c.corridor_id FROM corridors c
                           JOIN locations lo ON c.origin_location = lo.location_id
                           JOIN locations ld ON c.destination_location = ld.location_id
                           WHERE lo.system_name = %s AND ld.system_name = %s
                           AND c.corridor_type = 'gated' AND c.is_active = true
                           ORDER BY RANDOM() LIMIT %s""",
                        (loc_a_system, loc_b_system, parallel_gated - 2),  # Keep only 2 routes
                        fetch='all'
                    )
                    
                    for (corridor_id,) in excess_routes:
                        if random.random() < 0.3:  # 30% chance to break excess parallel routes
                            self.db.execute_query(
                                "UPDATE corridors SET is_active = false, last_shift = NOW() WHERE corridor_id = %s",
                                (corridor_id,)
                            )
                            complexity_results['routes_broken'] += 1
        
        return complexity_results

    async def _fix_overly_long_routes(self) -> Dict:
        """Fix any routes with travel times over 15 minutes (global max)"""
        
        fix_results = {
            'routes_fixed': 0,
            'routes_checked': 0
        }
        
        # Find routes over 15 minutes
        long_routes = self.db.execute_query(
            """SELECT corridor_id, name, origin_location, destination_location, travel_time
               FROM corridors 
               WHERE travel_time > 900 AND is_active = true
               ORDER BY travel_time DESC""",
            fetch='all'
        )
        
        fix_results['routes_checked'] = len(long_routes)
        
        for corridor_id, name, origin_id, dest_id, old_time in long_routes:
            # Get location info
            origin_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate, location_type FROM locations WHERE location_id = %s",
                (origin_id,), fetch='one'
            )
            dest_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate, location_type FROM locations WHERE location_id = %s", 
                (dest_id,), fetch='one'
            )
            
            if not origin_info or not dest_info:
                continue
                
            ox, oy, origin_type = origin_info
            dx, dy, dest_type = dest_info
            distance = math.sqrt((ox - dx)**2 + (oy - dy)**2)
            
            # Calculate new varied travel time
            if "Approach" in name or "Arrival" in name or "Local Space" in name:
                new_time = max(60, int(distance * 3) + 60)  # Local space: 1-3 minutes
            elif origin_type == 'gate' and dest_type == 'gate':
                # Gated corridors: ~8min average, 5-15min range with variation
                approach_time, main_time = self._calculate_gated_route_times(distance)
                new_time = main_time  # Use main corridor time for gate-to-gate
            else:
                # Ungated routes: ~6min average, 3-15min range with variation
                new_time = self._calculate_ungated_route_time(distance)
            
            # Update the corridor
            self.db.execute_query(
                "UPDATE corridors SET travel_time = %s WHERE corridor_id = %s",
                (new_time, corridor_id)
            )
            
            fix_results['routes_fixed'] += 1
        
        return fix_results

    async def _execute_fix_routes_logic(self) -> Dict:
        """Execute the same logic as the fix_routes command - for automatic corridor shifts"""
        return await self._fix_missing_local_space_routes()

    async def _fix_missing_local_space_routes(self) -> Dict:
        """Fix missing approach/arrival/departure routes for active gates"""
        
        route_fixes = {
            'missing_approaches': 0,
            'missing_arrivals': 0,
            'missing_departures': 0,
            'total_fixed': 0
        }
        
        # Batch fetch all required data upfront - ONLY ACTIVE GATES
        all_gates = self.db.execute_query(
            """SELECT location_id, name, x_coordinate, y_coordinate 
               FROM locations 
               WHERE location_type = 'gate' AND gate_status = 'active'""",
            fetch='all'
        )
        
        all_major_locations = self.db.execute_query(
            """SELECT location_id, name, x_coordinate, y_coordinate, location_type
               FROM locations
               WHERE location_type IN ('colony', 'space_station', 'outpost')""",
            fetch='all'
        )
        
        # Get ALL existing local space corridors in one query
        existing_local_corridors = self.db.execute_query(
            """SELECT origin_location, destination_location, name
               FROM corridors
               WHERE name LIKE '%Approach%' 
                  OR name LIKE '%Arrival%' 
                  OR name LIKE '%Departure%'""",
            fetch='all'
        )
        
        # Build lookup dictionaries for O(1) access
        existing_corridors_lookup = {}
        for origin, dest, name in existing_local_corridors:
            key = f"{origin}-{dest}"
            if 'Approach' in name:
                existing_corridors_lookup[f"approach_{key}"] = True
            elif 'Arrival' in name:
                existing_corridors_lookup[f"arrival_{key}"] = True
            elif 'Departure' in name:
                existing_corridors_lookup[f"departure_{key}"] = True
        
        # Process each gate
        for gate_id, gate_name, gx, gy in all_gates:
            # Find nearest major location
            nearest_loc = None
            min_distance = float('inf')
            
            for loc_id, loc_name, lx, ly, loc_type in all_major_locations:
                distance = math.sqrt((gx - lx) ** 2 + (gy - ly) ** 2)
                if distance < min_distance:
                    min_distance = distance
                    nearest_loc = (loc_id, loc_name, lx, ly)
            
            if not nearest_loc:
                continue
                
            loc_id, loc_name, lx, ly = nearest_loc
            
            # Check for missing Approach corridor
            approach_key = f"approach_{loc_id}-{gate_id}"
            if approach_key not in existing_corridors_lookup:
                approach_time = int(min_distance * 3) + 60
                fuel_cost = max(5, int(min_distance * 0.2))
                
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, corridor_type, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, 1, 'local_space', TRUE, TRUE)""",
                    (f"{gate_name} Approach", loc_id, gate_id, approach_time, fuel_cost)
                )
                route_fixes['missing_approaches'] += 1
            
            # Check for missing Arrival corridor
            arrival_key = f"arrival_{gate_id}-{loc_id}"
            if arrival_key not in existing_corridors_lookup:
                arrival_time = int(min_distance * 3) + 60
                fuel_cost = max(5, int(min_distance * 0.2))
                
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, corridor_type, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, 1, 'local_space', TRUE, TRUE)""",
                    (f"{gate_name} Arrival", gate_id, loc_id, arrival_time, fuel_cost)
                )
                route_fixes['missing_arrivals'] += 1
        
        # Check for missing return departures - batch fetch all gated corridors
        gated_corridors = self.db.execute_query(
            """SELECT DISTINCT c.corridor_id, c.name, c.origin_location, c.destination_location,
                      lo.name as origin_name, ld.name as dest_name
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE lo.location_type = 'gate' 
               AND ld.location_type = 'gate'
               AND c.name NOT LIKE '%Return%'
               AND c.name NOT LIKE '%Approach%'
               AND c.name NOT LIKE '%Arrival%'
               AND c.name NOT LIKE '%Departure%'
               AND c.corridor_type != 'ungated'
               AND c.is_active = true""",
            fetch='all'
        )
        
        # Get all gate-to-location connections in one query
        gate_connections = self.db.execute_query(
            """SELECT c.origin_location as gate_id, c.destination_location as loc_id,
                      l.name as loc_name, l.x_coordinate, l.y_coordinate,
                      g.x_coordinate as gate_x, g.y_coordinate as gate_y
               FROM corridors c
               JOIN locations l ON c.destination_location = l.location_id
               JOIN locations g ON c.origin_location = g.location_id
               WHERE c.name LIKE '%Arrival%'
               AND l.location_type != 'gate'
               AND g.location_type = 'gate'""",
            fetch='all'
        )
        
        # Build gate connection lookup
        gate_to_locations = {}
        for gate_id, loc_id, loc_name, lx, ly, gx, gy in gate_connections:
            if gate_id not in gate_to_locations:
                gate_to_locations[gate_id] = []
            gate_to_locations[gate_id].append((loc_id, loc_name, lx, ly, gx, gy))
        
        # Process return departures
        for corridor_id, base_name, origin_gate, dest_gate, origin_name, dest_name in gated_corridors:
            if dest_gate in gate_to_locations:
                for loc_id, loc_name, lx, ly, gx, gy in gate_to_locations[dest_gate]:
                    departure_name = f"{base_name} Return Departure"
                    
                    # Check if this specific departure exists
                    exists = any(
                        origin == loc_id and dest == dest_gate and departure_name in name
                        for origin, dest, name in existing_local_corridors
                    )
                    
                    if not exists:
                        distance = math.sqrt((lx - gx) ** 2 + (ly - gy) ** 2)
                        dep_time = int(distance * 3) + 60
                        fuel_cost = max(5, int(distance * 0.2))
                        
                        self.db.execute_query(
                            """INSERT INTO corridors 
                               (name, origin_location, destination_location, travel_time,
                                fuel_cost, danger_level, corridor_type, is_active, is_generated)
                               VALUES (%s, %s, %s, %s, %s, 1, 'local_space', TRUE, TRUE)""",
                            (departure_name, loc_id, dest_gate, dep_time, fuel_cost)
                        )
                        route_fixes['missing_departures'] += 1
        
        route_fixes['total_fixed'] = route_fixes['missing_approaches'] + route_fixes['missing_arrivals'] + route_fixes['missing_departures']
        
        return route_fixes

    async def _replenish_dormant_corridors(self, intensity: int):
        """Create new dormant corridors to maintain future shift potential, heavily biased toward gate-to-gate routes"""
        
        # Get gates and major locations separately for targeted creation
        gates = self.db.execute_query(
            "SELECT location_id, name, x_coordinate, y_coordinate, system_name FROM locations WHERE location_type = 'gate'",
            fetch='all'
        )
        
        major_locations = self.db.execute_query(
            "SELECT location_id, name, x_coordinate, y_coordinate, system_name, location_type FROM locations WHERE location_type IN ('colony', 'space_station', 'outpost')",
            fetch='all'
        )
        
        # Calculate how many dormant corridors to create (heavily biased toward gate-to-gate)
        total_gates = len(gates)
        
        # Target ratio: for every 2-3 gates, ensure 1-4 gated corridors are available (including dormant)
        current_gated_active = self.db.execute_query(
            """SELECT COUNT(*) FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE c.corridor_type = 'gated' AND c.is_active = true
               AND lo.location_type = 'gate' AND ld.location_type = 'gate'
               AND lo.system_name != ld.system_name""",
            fetch='one'
        )[0]
        
        current_gated_dormant = self.db.execute_query(
            """SELECT COUNT(*) FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE c.corridor_type = 'gated' AND c.is_active = false
               AND lo.location_type = 'gate' AND ld.location_type = 'gate'
               AND lo.system_name != ld.system_name""",
            fetch='one'
        )[0]
        
        total_gated_corridors = current_gated_active + current_gated_dormant
        target_gated_corridors = max(total_gates // 2, total_gates * 2 // 3)  # Aim for robust connectivity
        
        gate_corridors_needed = max(0, target_gated_corridors - total_gated_corridors)
        other_corridors_needed = max(1, intensity)  # Minimal non-gate corridors
        
        print(f"🔧 Replenishing dormant pool: need {gate_corridors_needed} more gate-to-gate, {other_corridors_needed} other routes")
        
        created_gated = 0
        created_other = 0
        
        # Priority 1: Create gate-to-gate dormant corridors
        if gate_corridors_needed > 0 and len(gates) >= 2:
            for _ in range(gate_corridors_needed * 3):  # More attempts than needed
                if created_gated >= gate_corridors_needed:
                    break
                
                gate_a, gate_b = random.sample(gates, 2)
                gate_a_id, gate_a_name, gate_a_x, gate_a_y, gate_a_system = gate_a
                gate_b_id, gate_b_name, gate_b_x, gate_b_y, gate_b_system = gate_b
                
                # Only create cross-system gate connections (per rules)
                if gate_a_system == gate_b_system:
                    continue
                
                # Check if they already have any corridor between them
                existing = self.db.execute_query(
                    """SELECT COUNT(*) FROM corridors 
                       WHERE (origin_location = %s AND destination_location = %s) 
                          OR (origin_location = %s AND destination_location = %s)""",
                    (gate_a_id, gate_b_id, gate_b_id, gate_a_id),
                    fetch='one'
                )[0]
                
                if existing > 0:
                    continue
                
                distance = math.sqrt((gate_a_x - gate_b_x) ** 2 + (gate_a_y - gate_b_y) ** 2)
                if distance > 150:  # Don't create extremely long routes
                    continue
                
                # Create dormant gated corridor pair
                corridor_name = f"{gate_a_name} - {gate_b_name} Route"
                fuel_cost = max(15, int(distance * 1.2) + 10)
                danger = random.randint(2, 4)  # Gated corridors are safer
                approach_time, travel_time = self._calculate_gated_route_times(distance)
                # Use main corridor time for gate-to-gate routes
                
                self.db.execute_query(
                    '''INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time, fuel_cost, 
                        danger_level, corridor_type, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, %s, 'gated', FALSE, TRUE)''',
                    (f"{corridor_name} (Dormant)", gate_a_id, gate_b_id, travel_time, fuel_cost, danger)
                )
                
                self.db.execute_query(
                    '''INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time, fuel_cost, 
                        danger_level, corridor_type, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, %s, 'gated', FALSE, TRUE)''',
                    (f"{corridor_name} Return (Dormant)", gate_b_id, gate_a_id, travel_time, fuel_cost, danger)
                )
                
                created_gated += 1
        
        # Priority 2: Create some other dormant corridors (ungated routes for variety)
        all_locations = []
        for gate_id, gate_name, gate_x, gate_y, gate_system in gates:
            all_locations.append({'id': gate_id, 'name': gate_name, 'type': 'gate', 'x': gate_x, 'y': gate_y, 'system': gate_system})
        for loc_id, loc_name, loc_x, loc_y, loc_system, loc_type in major_locations:
            all_locations.append({'id': loc_id, 'name': loc_name, 'type': loc_type, 'x': loc_x, 'y': loc_y, 'system': loc_system})
        
        for _ in range(other_corridors_needed * 2):
            if created_other >= other_corridors_needed:
                break
                
            if len(all_locations) < 2:
                break
                
            loc_a, loc_b = random.sample(all_locations, 2)
            
            # Skip if both are gates (we handled gate-to-gate above)
            if loc_a['type'] == 'gate' and loc_b['type'] == 'gate':
                continue
            
            # Check if they already have any corridor between them
            existing = self.db.execute_query(
                """SELECT COUNT(*) FROM corridors 
                   WHERE (origin_location = %s AND destination_location = %s) 
                      OR (origin_location = %s AND destination_location = %s)""",
                (loc_a['id'], loc_b['id'], loc_b['id'], loc_a['id']),
                fetch='one'
            )[0]
            
            if existing > 0:
                continue
            
            distance = math.sqrt((loc_a['x'] - loc_b['x']) ** 2 + (loc_a['y'] - loc_b['y']) ** 2)
            if distance > 120:
                continue
            
            # Create dormant ungated corridor pair
            corridor_name = f"{loc_a['name']} - {loc_b['name']} Route"
            fuel_cost = max(10, int(distance * 0.8) + 5)
            danger = random.randint(3, 5)  # Ungated routes are more dangerous
            travel_time = self._calculate_ungated_route_time(distance)
            
            self.db.execute_query(
                '''INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time, fuel_cost, 
                    danger_level, corridor_type, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, %s, 'ungated', FALSE, TRUE)''',
                (f"{corridor_name} (Dormant)", loc_a['id'], loc_b['id'], travel_time, fuel_cost, danger)
            )
            
            self.db.execute_query(
                '''INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time, fuel_cost, 
                    danger_level, corridor_type, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, %s, 'ungated', FALSE, TRUE)''',
                (f"{corridor_name} Return (Dormant)", loc_b['id'], loc_a['id'], travel_time, fuel_cost, danger)
            )
            
            created_other += 1
        
        if created_gated > 0 or created_other > 0:
            print(f"🔧 Created {created_gated} dormant gated corridors and {created_other} dormant ungated corridors")

    async def _analyze_connectivity_post_shift(self) -> str:
        """Analyze connectivity after corridor shifts"""
        
        locations = self.db.execute_query(
            "SELECT location_id FROM locations",
            fetch='all'
        )
        
        if not locations:
            return "No locations found"
        
        # Build graph of active corridors
        graph = {loc[0]: set() for loc in locations}
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = true",
            fetch='all'
        )
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        total_locations = len(locations)
        largest_component_size = max(len(comp) for comp in components) if components else 0
        connectivity_percent = (largest_component_size / total_locations) * 100 if total_locations > 0 else 0
        
        if len(components) == 1:
            return f"✅ Fully connected ({total_locations} locations)"
        else:
            return f"⚠️ {len(components)} clusters, largest: {largest_component_size}/{total_locations} ({connectivity_percent:.1f}%)"

    async def _notify_travelers_of_shifts(self, results: Dict):
        """Notify active travelers about corridor shifts"""
        
        # MEMORY LEAK FIX: Handle cleared affected_locations set
        if not results.get('affected_locations') or len(results['affected_locations']) == 0:
            # If no affected locations or set was cleared, skip notification
            return
        
        # Find travelers who might be affected
        affected_travelers = self.db.execute_query(
            """SELECT DISTINCT ts.user_id, ts.temp_channel_id, c.name as corridor_name
               FROM travel_sessions ts
               JOIN corridors c ON ts.corridor_id = c.corridor_id
               WHERE ts.status = 'traveling' 
                 AND (ts.origin_location IN ({}) OR ts.destination_location IN ({}))""".format(
                     ','.join(map(str, results['affected_locations'])),
                     ','.join(map(str, results['affected_locations']))
                 ),
            fetch='all'
        )
        
        for user_id, channel_id, corridor_name in affected_travelers:
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🌌 Corridor Shift Detected",
                        description="Galactic infrastructure changes detected in nearby space.",
                        color=0x800080
                    )
                    embed.add_field(
                        name="Current Journey",
                        value=f"Your transit via {corridor_name} continues normally.",
                        inline=False
                    )
                    embed.add_field(
                        name="Advisory",
                        value="Route availability may have changed at your destination. Check `/travel routes` upon arrival.",
                        inline=False
                    )
                    
                    try:
                        await channel.send(embed=embed)
                    except:
                        pass  # Channel might be deleted or inaccessible
    @galaxy_group.command(name="analyze_connectivity", description="Analyze current galaxy connectivity")
    async def analyze_connectivity(self, interaction: discord.Interaction):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            analysis = await self._perform_connectivity_analysis()
            
            embed = discord.Embed(
                title="📊 Galaxy Connectivity Analysis",
                description="Current state of galactic infrastructure",
                color=0x4169E1
            )
            
            embed.add_field(
                name="🗺️ Overall Connectivity",
                value=analysis['overall_status'],
                inline=False
            )
            
            embed.add_field(
                name="📈 Statistics",
                value=analysis['statistics'],
                inline=False
            )
            
            if analysis['isolated_locations']:
                embed.add_field(
                    name="⚠️ Isolated Locations",
                    value=analysis['isolated_locations'][:1000] + "..." if len(analysis['isolated_locations']) > 1000 else analysis['isolated_locations'],
                    inline=False
                )
            
            embed.add_field(
                name="🔮 Shift Potential",
                value=analysis['shift_potential'],
                inline=False
            )
            
            if analysis['recommendations']:
                embed.add_field(
                    name="💡 Recommendations",
                    value=analysis['recommendations'],
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error analyzing connectivity: {str(e)}")

    async def _perform_connectivity_analysis(self) -> Dict:
        """Perform detailed connectivity analysis"""
        
        # Get all locations and corridors
        locations = self.db.execute_query(
            "SELECT location_id, name, location_type FROM locations",
            fetch='all'
        )
        
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = true",
            fetch='all'
        )
        
        dormant_corridors = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE is_active = false",
            fetch='one'
        )[0]
        
        if not locations:
            return {"overall_status": "No locations found", "statistics": "", "isolated_locations": "", "shift_potential": "", "recommendations": ""}
        
        # Build connectivity graph
        graph = {loc[0]: set() for loc in locations}
        location_names = {loc[0]: f"{loc[1]} ({loc[2]})" for loc in locations}
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        # Analyze results
        total_locations = len(locations)
        largest_component = max(components, key=len) if components else set()
        connectivity_percent = (len(largest_component) / total_locations) * 100 if total_locations > 0 else 0
        
        # Overall status
        if len(components) == 1:
            overall_status = f"✅ **Fully Connected**\nAll {total_locations} locations are reachable from each other."
        else:
            overall_status = f"⚠️ **Fragmented Network**\n{len(components)} separate clusters detected.\nLargest cluster: {len(largest_component)}/{total_locations} locations ({connectivity_percent:.1f}%)"
        
        # Statistics
        connection_counts = [len(graph[loc_id]) for loc_id in graph]
        avg_connections = sum(connection_counts) / len(connection_counts) if connection_counts else 0
        
        statistics = f"""**Active Corridors:** {len(active_corridors)}
    **Dormant Corridors:** {dormant_corridors}
    **Average Connections per Location:** {avg_connections:.1f}
    **Most Connected:** {max(connection_counts) if connection_counts else 0} corridors
    **Least Connected:** {min(connection_counts) if connection_counts else 0} corridors"""
        
        # Isolated locations
        isolated_locations = ""
        if len(components) > 1:
            small_clusters = [comp for comp in components if len(comp) < len(largest_component)]
            if small_clusters:
                isolated_list = []
                for cluster in small_clusters:
                    cluster_names = [location_names[loc_id] for loc_id in cluster]
                    isolated_list.append(f"• Cluster of {len(cluster)}: {', '.join(cluster_names[:3])}" + ("..." if len(cluster) > 3 else ""))
                isolated_locations = "\n".join(isolated_list[:10])  # Limit to prevent spam
        
        if not isolated_locations:
            isolated_locations = "None - all locations are in the main network"
        
        # Shift potential
        shift_potential = f"""**Dormant Routes Available:** {dormant_corridors}
    **Potential for New Connections:** {'High' if dormant_corridors > total_locations else 'Moderate' if dormant_corridors > total_locations // 2 else 'Low'}
    **Risk Level:** {'Low' if len(components) == 1 else 'High'}"""
        
        # Recommendations
        recommendations = []
        if len(components) > 1:
            recommendations.append("• Use `/galaxy shift_corridors` to activate dormant routes")
            recommendations.append("• Consider manual route creation between isolated clusters")
        
        if avg_connections < 2.5:
            recommendations.append("• Overall connectivity is low - consider more corridor generation")
        
        if dormant_corridors < total_locations:
            recommendations.append("• Low dormant corridor count - future shifts may be limited")
        
        recommendations_text = "\n".join(recommendations) if recommendations else "Galaxy connectivity is healthy"
        
        return {
            "overall_status": overall_status,
            "statistics": statistics,
            "isolated_locations": isolated_locations,
            "shift_potential": shift_potential,
            "recommendations": recommendations_text
        }

    @galaxy_group.command(name="check_density", description="Check corridor density and identify overcrowding issues")
    async def check_corridor_density(self, interaction: discord.Interaction):
        """Check corridor density and identify overcrowding issues"""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            density_info = await self._check_corridor_density()
            
            if density_info['status'] == 'error':
                await interaction.followup.send(
                    f"❌ Error checking density: {density_info['message']}", 
                    ephemeral=True
                )
                return
            
            # Create status embed
            status_colors = {
                'healthy': 0x00ff00,
                'dense': 0xffa500, 
                'overcrowded': 0xff0000
            }
            
            embed = discord.Embed(
                title="🌌 Corridor Density Analysis",
                description=f"Galaxy corridor density status: **{density_info['status'].upper()}**",
                color=status_colors.get(density_info['status'], 0x888888)
            )
            
            # Add statistics
            embed.add_field(
                name="📊 Current Statistics",
                value=f"• Total Locations: {density_info['total_locations']}\n"
                      f"• Active Corridors: {density_info['active_corridors']}\n"
                      f"• Dormant Corridors: {density_info['dormant_corridors']}\n"
                      f"• Active Ratio: {density_info['active_ratio']:.1f}x locations\n"
                      f"• Total Ratio: {density_info['total_ratio']:.1f}x locations",
                inline=False
            )
            
            # Add issues if any
            if density_info['issues']:
                embed.add_field(
                    name="⚠️ Issues Detected",
                    value="\n".join([f"• {issue}" for issue in density_info['issues']]),
                    inline=False
                )
            
            # Add recommendations
            recommendations = []
            if density_info['status'] == 'overcrowded':
                recommendations.append("Use `/galaxy cleanup_corridors` to remove excess routes")
                recommendations.append("Reduce corridor generation in future expansions")
            elif density_info['status'] == 'dense':
                recommendations.append("Monitor corridor growth during shifts")
                recommendations.append("Consider selective cleanup if needed")
            else:
                recommendations.append("Corridor density is healthy!")
            
            if recommendations:
                embed.add_field(
                    name="💡 Recommendations",
                    value="\n".join([f"• {rec}" for rec in recommendations]),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Error in check_corridor_density: {e}")
            await interaction.followup.send(
                f"❌ Error checking corridor density: {e}",
                ephemeral=True
            )

    @galaxy_group.command(name="cleanup_corridors", description="Clean up excess corridors to reduce overcrowding")
    @app_commands.describe(
        max_cleanup="Maximum number of corridors to clean up (default: 50)"
    )
    async def cleanup_corridors(self, interaction: discord.Interaction, max_cleanup: int = 50):
        """Clean up excess corridors to reduce overcrowding"""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate max_cleanup
            max_cleanup = max(1, min(max_cleanup, 2000))  # Clamp between 1-2000
            
            cleanup_result = await self._cleanup_excess_corridors(max_cleanup)
            
            embed = discord.Embed(
                title="🧹 Corridor Cleanup Results",
                color=0x00ff00 if cleanup_result['cleaned'] > 0 else 0x888888
            )
            
            embed.add_field(
                name="📊 Cleanup Summary",
                value=f"• Corridors Cleaned: {cleanup_result['cleaned']}\n"
                      f"• Status: {cleanup_result['message']}",
                inline=False
            )
            
            # Show before/after if cleanup occurred
            if cleanup_result['cleaned'] > 0 and 'new_density' in cleanup_result:
                new_density = cleanup_result['new_density']
                embed.add_field(
                    name="📈 Updated Statistics",
                    value=f"• New Status: **{new_density['status'].upper()}**\n"
                          f"• Active Corridors: {new_density['active_corridors']}\n"
                          f"• Dormant Corridors: {new_density['dormant_corridors']}\n"
                          f"• Active Ratio: {new_density['active_ratio']:.1f}x locations\n"
                          f"• Total Ratio: {new_density['total_ratio']:.1f}x locations",
                    inline=False
                )
                
                if new_density['issues']:
                    embed.add_field(
                        name="⚠️ Remaining Issues",
                        value="\n".join([f"• {issue}" for issue in new_density['issues']]),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="✅ Resolution", 
                        value="All density issues have been resolved!",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Error in cleanup_corridors: {e}")
            await interaction.followup.send(
                f"❌ Error during corridor cleanup: {e}",
                ephemeral=True
            )

    async def _check_corridor_density(self) -> Dict:
        """Check corridor density and identify overcrowding issues"""
        
        # Get basic stats
        total_locations = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
        active_corridors = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = true", fetch='one')[0]
        dormant_corridors = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = false", fetch='one')[0]
        
        if not total_locations:
            return {"status": "error", "message": "No locations found"}
        
        active_ratio = active_corridors / total_locations
        total_ratio = (active_corridors + dormant_corridors) / total_locations
        
        # Check gate corridor compliance per ROUTE-LOCATION-RULES.md
        gates = self.db.execute_query("""
            SELECT location_id, name FROM locations 
            WHERE location_type = 'gate'
        """, fetch='all')
        
        gate_corridor_violations = 0
        for gate_id, gate_name in gates:
            # Count gated corridors for this gate using the new corridor_type column
            gate_corridors = self.db.execute_query("""
                SELECT COUNT(*) FROM corridors 
                WHERE (origin_location = %s OR destination_location = %s) 
                AND is_active = true
                AND corridor_type = 'gated'
            """, (gate_id, gate_id), fetch='one')[0]
            
            # Rule: for every 2-3 active gates, no more than 1-4 gated corridors
            if gate_corridors > 4:
                gate_corridor_violations += 1
        
        # Density assessment
        density_status = "healthy"
        issues = []
        
        if active_ratio > 3:  # Too many active corridors
            density_status = "overcrowded"
            issues.append(f"Active corridor ratio too high: {active_ratio:.1f}x locations")
        elif active_ratio > 2:
            density_status = "dense"
            issues.append(f"Active corridor density high: {active_ratio:.1f}x locations")
        
        if total_ratio > 5:  # Total corridors way too high
            density_status = "overcrowded"
            issues.append(f"Total corridor ratio excessive: {total_ratio:.1f}x locations")
        elif total_ratio > 3:
            if density_status == "healthy":
                density_status = "dense"
            issues.append(f"Total corridor count high: {total_ratio:.1f}x locations")
        
        if gate_corridor_violations > 0:
            issues.append(f"{gate_corridor_violations} gates violate corridor rules")
        
        return {
            "status": density_status,
            "active_ratio": active_ratio,
            "total_ratio": total_ratio,
            "active_corridors": active_corridors,
            "dormant_corridors": dormant_corridors,
            "total_locations": total_locations,
            "gate_violations": gate_corridor_violations,
            "issues": issues
        }

    async def _cleanup_excess_corridors(self, max_cleanup: int = 50) -> Dict:
        """Clean up excess corridors to reduce overcrowding"""
        import asyncio
        
        density_check = await self._check_corridor_density()
        
        if density_check['status'] == 'healthy':
            return {"cleaned": 0, "message": "No cleanup needed - density is healthy"}
        
        cleanup_count = 0
        
        # First: Remove dormant corridors that are too numerous
        if density_check['total_ratio'] > 3:
            target_dormant = int(density_check['total_locations'] * 1.5)  # Target 1.5x locations
            excess_dormant = max(0, density_check['dormant_corridors'] - target_dormant)
            
            if excess_dormant > 0:
                dormant_to_remove = min(excess_dormant, max_cleanup // 2)
                
                # Remove shortest/least strategic dormant corridors first
                corridors_to_remove = self.db.execute_query("""
                    SELECT corridor_id FROM corridors 
                    WHERE is_active = false 
                    ORDER BY travel_time ASC, fuel_cost ASC
                    LIMIT %s
                """, (dormant_to_remove,), fetch='all')
                
                # Batch delete operations to prevent locks
                if corridors_to_remove:
                    batch_operations = []
                    for (corridor_id,) in corridors_to_remove:
                        batch_operations.append(("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,)))
                    
                    # Execute in small batches with yielding
                    batch_size = 10
                    for i in range(0, len(batch_operations), batch_size):
                        batch = batch_operations[i:i + batch_size]
                        for query, params in batch:
                            self.db.execute_query(query, params)
                            cleanup_count += 1
                        
                        # Yield control to prevent blocking
                        await asyncio.sleep(0.01)
        
        # Second: Deactivate excess active corridors if still overcrowded
        remaining_cleanup = max_cleanup - cleanup_count
        if remaining_cleanup > 0 and density_check['active_ratio'] > 2:
            target_active = int(density_check['total_locations'] * 2)  # Target 2x locations
            excess_active = max(0, density_check['active_corridors'] - target_active)
            
            if excess_active > 0:
                active_to_deactivate = min(excess_active, remaining_cleanup)
                
                # Deactivate non-critical corridors (avoid isolation)
                corridors_to_deactivate = self.db.execute_query("""
                    SELECT corridor_id, origin_location, destination_location FROM corridors 
                    WHERE is_active = true 
                    AND corridor_type != 'local_space'
                    ORDER BY travel_time DESC, danger_level DESC
                    LIMIT %s
                """, (active_to_deactivate * 2,), fetch='all')  # Get more candidates
                
                # Batch deactivation operations to prevent locks
                deactivation_operations = []
                for corridor_id, origin_id, dest_id in corridors_to_deactivate:
                    if cleanup_count >= max_cleanup:
                        break
                    
                    # Check if deactivation would isolate a location
                    if not self._would_isolate_location(corridor_id, origin_id, dest_id):
                        deactivation_operations.append((
                            "UPDATE corridors SET is_active = false, last_shift = NOW() WHERE corridor_id = %s",
                            (corridor_id,)
                        ))
                        cleanup_count += 1
                
                # Execute deactivations in small batches with yielding
                if deactivation_operations:
                    batch_size = 10
                    for i in range(0, len(deactivation_operations), batch_size):
                        batch = deactivation_operations[i:i + batch_size]
                        for query, params in batch:
                            self.db.execute_query(query, params)
                        
                        # Yield control to prevent blocking
                        await asyncio.sleep(0.01)
        
        return {
            "cleaned": cleanup_count,
            "message": f"Cleaned up {cleanup_count} excess corridors",
            "new_density": await self._check_corridor_density()
        }

    def _determine_corridor_type(self, origin_id: int, dest_id: int, corridor_name: str) -> str:
        """Determine if a corridor should be gated or ungated based on ROUTE-LOCATION-RULES.md"""
        
        # Get location types and system info for both endpoints
        origin_data = self.db.execute_query(
            "SELECT location_type, system_name FROM locations WHERE location_id = %s", 
            (origin_id,), fetch='one'
        )
        dest_data = self.db.execute_query(
            "SELECT location_type, system_name FROM locations WHERE location_id = %s", 
            (dest_id,), fetch='one'
        )
        
        if not origin_data or not dest_data:
            return 'ungated'  # Default to ungated if location data missing
            
        origin_type, origin_system = origin_data
        dest_type, dest_system = dest_data
        same_system = origin_system == dest_system
        
        # Local space routes (name-based detection or same system connections)
        if any(keyword in corridor_name.lower() for keyword in ['local space', 'approach', 'arrival', 'departure']):
            return 'local_space'
        
        # Rules from ROUTE-LOCATION-RULES.md:
        # - Gated corridors should ONLY connect gates to other gates
        # - Major locations should ONLY connect to LOCAL gates via local space
        # - Corridors (gated/ungated) should NEVER directly connect major locations to gates
        
        # CRITICAL FIX: Major location ↔ Gate connections must ALWAYS be local_space if in same system
        if (origin_type in ['colony', 'space_station', 'outpost'] and dest_type == 'gate') or \
           (origin_type == 'gate' and dest_type in ['colony', 'space_station', 'outpost']):
            if same_system:
                return 'local_space'  # Major location to local gate = local space ONLY
            else:
                # Major location to distant gate should be ungated (rare but allowed)
                return 'ungated'
        
        # Gate to gate connections
        if origin_type == 'gate' and dest_type == 'gate':
            if same_system:
                return 'local_space'  # Gates in same system = local space
            else:
                return 'gated'  # Gates in different systems = gated corridor
        
        # Major location to major location connections
        else:
            # Major location to major location = ungated (risky direct routes)
            return 'ungated'

    async def _update_corridor_types_during_activation(self, corridors_to_activate: list):
        """Update corridor types when activating dormant corridors - now simplified with corridor_type column"""
        
        # Since we now have corridor_type column, we just need to ensure
        # corridor types are correctly set when they activate (they should already be correct from creation)
        # This function is now mainly a placeholder for future corridor type adjustments during activation
        
        for corridor_data in corridors_to_activate:
            corridor_id = corridor_data[0]
            corridor_name = corridor_data[1] 
            origin_id = corridor_data[2]
            dest_id = corridor_data[3]
            
            # Verify and update corridor type if needed
            correct_type = self._determine_corridor_type(origin_id, dest_id, corridor_name)
            
            # Update the corridor_type in the database if it's incorrect
            self.db.execute_query(
                "UPDATE corridors SET corridor_type = %s WHERE corridor_id = %s",
                (correct_type, corridor_id)
            )
    async def _generate_sub_locations_for_all_locations(self, conn, all_locations: List[Dict]) -> int:
        """Generates persistent sub-locations for all locations in bulk."""
        from utils.sub_locations import SubLocationManager
        
        sub_manager = SubLocationManager(self.bot)
        sub_locations_to_insert = []
        
        for location in all_locations:
            # The manager returns a list of sub-locations to be created
            generated_subs = await sub_manager.get_persistent_sub_locations_data(
                location['id'], 
                location['type'], 
                location['wealth_level'],
                location.get('is_derelict', False)
            )
            sub_locations_to_insert.extend(generated_subs)
            
        if sub_locations_to_insert:
            query = '''INSERT INTO sub_locations 
                       (parent_location_id, name, sub_type, description) 
                       VALUES (%s, %s, %s, %s)'''
            self.db.executemany_in_transaction(conn, query, sub_locations_to_insert)
            print(f"🏢 Generated {len(sub_locations_to_insert)} sub-locations in total.")
            
        return len(sub_locations_to_insert)
        
    async def _generate_gates_for_routes(self, conn, routes: List[Dict], major_locations: List[Dict]) -> List[Dict]:
        """Generate gates for routes with optimized batching and yielding"""
        if not routes:
            return []
        
        # Commit current transaction to avoid long locks
        if conn:
            self.db.commit_transaction(conn)
            conn = None
        
        print(f"🚪 Generating gates for {len(routes)} routes...")
        
        gates = []
        used_names = set()
        gates_to_create = []
        
        # First pass: determine which routes get gates and prepare gate data
        for i, route in enumerate(routes):
            gate_chance = 0.5
            if random.random() < gate_chance:
                # Pre-generate gate names to avoid conflicts
                origin_name = self._generate_unique_gate_name(route['from'], used_names)
                dest_name = self._generate_unique_gate_name(route['to'], used_names)
                
                used_names.add(origin_name)
                used_names.add(dest_name)
                
                gates_to_create.append({
                    'route_index': i,
                    'origin_data': self._create_gate_data(route['from'], origin_name),
                    'dest_data': self._create_gate_data(route['to'], dest_name)
                })
                
                route['has_gates'] = True
            else:
                route['has_gates'] = False
            
            # Yield every 20 routes in planning phase
            if i % 20 == 0:
                await asyncio.sleep(0.01)
        
        print(f"🚪 Creating {len(gates_to_create) * 2} gate locations...")
        
        # Second pass: create gates in small batches
        batch_size = 10  # Small batches to avoid long transactions
        
        for batch_start in range(0, len(gates_to_create), batch_size):
            batch_end = min(batch_start + batch_size, len(gates_to_create))
            batch = gates_to_create[batch_start:batch_end]
            
            # Create gates in independent micro-transaction
            batch_gates = await self._create_gate_batch(batch, routes)
            gates.extend(batch_gates)
            
            # Progress reporting
            progress = ((batch_end) / len(gates_to_create)) * 100
            if batch_start % 50 == 0:  # Report every 50 items processed
                print(f"    🚪 Gate creation progress: {progress:.0f}% ({batch_end}/{len(gates_to_create)} routes)")
            
            # Yield control after each batch
            await asyncio.sleep(0.05)
        
        print(f"✅ Created {len(gates)} gate locations")
        return gates

    def _generate_unique_gate_name(self, location: Dict, used_names: set) -> str:
        """Generate unique gate name more efficiently"""
        location_name = location['name']
        
        # Pre-generate several candidates to reduce conflicts
        candidates = [
            f"{location_name}-{random.choice(self.location_names)} {random.choice(self.gate_names)}",
            f"{location_name} {random.choice(self.gate_names)}",
            f"{random.choice(self.location_names)} {random.choice(self.gate_names)}",
            f"{location_name}-{random.choice(['Alpha', 'Beta', 'Gamma', 'Delta'])} {random.choice(self.gate_names)}"
        ]
        
        # Try candidates first
        for candidate in candidates:
            if candidate not in used_names:
                return candidate
        
        # Fallback with counter if all candidates taken
        base_name = f"{location_name} {random.choice(self.gate_names)}"
        counter = 1
        while f"{base_name} {counter}" in used_names:
            counter += 1
        
        return f"{base_name} {counter}"
    
    def _create_gate_data(self, location: Dict, gate_name: str) -> Dict:
        """Create gate data without database interaction"""
        import math
        
        # Position gate close to but not overlapping the location
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(3, 8)
        
        gate_x = location['x_coordinate'] + distance * math.cos(angle)
        gate_y = location['y_coordinate'] + distance * math.sin(angle)
        
        return {
            'name': gate_name,
            'type': 'gate',
            'x_coordinate': gate_x,
            'y_coordinate': gate_y,
            'system_name': location['system_name'],
            'description': f"Transit gate providing safe passage to and from {location['name']}. Features decontamination facilities and basic services.",
            'wealth_level': min(location['wealth_level'] + 1, 8),
            'population': random.randint(15, 40),
            'has_jobs': False,
            'has_shops': True,
            'has_medical': True,
            'has_repairs': True,
            'has_fuel': True,
            'has_upgrades': False,
            'is_generated': True,
            'parent_location': location['id']
        }
    async def _create_gate_batch(self, gate_batch: List[Dict], routes: List[Dict]) -> List[Dict]:
        """Create a batch of gates in independent transaction with retry logic"""
        created_gates = []
        
        # Retry logic for database lock issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait a bit if this is a retry
                if attempt > 0:
                    await asyncio.sleep(0.5 * attempt)
                
                # Use independent micro-transaction
                micro_conn = self.db.begin_transaction()
                break
            except RuntimeError as e:
                if "database lock" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Database lock in gate creation, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    print(f"❌ Failed to acquire database lock for gate creation: {e}")
                    return []  # Return empty list instead of crashing
        try:
            for gate_info in gate_batch:
                route_index = gate_info['route_index']
                route = routes[route_index]
                
                # Create origin gate
                origin_data = gate_info['origin_data']
                origin_id = self._save_location_to_db(micro_conn, origin_data)
                origin_data['id'] = origin_id
                created_gates.append(origin_data)
                
                # Create destination gate
                dest_data = gate_info['dest_data']
                dest_id = self._save_location_to_db(micro_conn, dest_data)
                dest_data['id'] = dest_id
                created_gates.append(dest_data)
                
                # Update route with gate references
                route['origin_gate'] = origin_data
                route['destination_gate'] = dest_data
            
            self.db.commit_transaction(micro_conn)
            
        except Exception as e:
            self.db.rollback_transaction(micro_conn)
            print(f"❌ Error creating gate batch: {e}")
            # Return empty list for this batch
            return []
        finally:
            micro_conn = None
        
        return created_gates    
    def _create_gate_near_location(self, location: Dict, gate_type: str, used_names: set) -> Dict:
        """Create a gate near a major location"""
        
        # Position gate close to but not overlapping the location
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(3, 8)  # Close but separate
        
        gate_x = location['x_coordinate'] + distance * math.cos(angle)
        gate_y = location['y_coordinate'] + distance * math.sin(angle)
        
        name = ""
        attempts = 0
        while attempts < 50:
            # Randomly select a type name from your gate_names list (e.g., "Portal", "Junction")
            gate_type_name = random.choice(self.gate_names)
            # Randomly select a descriptor from your location_names list (e.g., "Hope", "Meridian")
            descriptor = random.choice(self.location_names)
            
            # Combine them for a unique name like "Earth-Hope Portal"
            name = f"{location['name']}-{descriptor} {gate_type_name}"
            
            if name not in used_names:
                break  # Found a unique name
            attempts += 1
        
        # A fallback for the very rare case of 50 failed attempts
        if attempts == 50:
            counter = 1
            while f"{name} {counter}" in used_names:
                counter += 1
            name = f"{name} {counter}"


        # Gates always have maintenance crews - ensure minimum population for NPCs
        gate_population = random.randint(15, 40)  # Small operational crew
        
        return {
            'name': name,
            'type': 'gate',
            'x_coordinate': gate_x,
            'y_coordinate': gate_y,
            'system_name': location['system_name'],
            'description': f"Transit gate providing safe passage to and from {location['name']}. Features decontamination facilities and basic services.",
            'wealth_level': min(location['wealth_level'] + 1, 8),  # Gates are well-maintained
            'population': gate_population,  # Ensure adequate population for NPCs
            'has_jobs': False,  # Gates don't have jobs
            'has_shops': True,   # Basic supplies
            'has_medical': True, # Decontamination 
            'has_repairs': True, # Ship maintenance
            'has_fuel': True,    # Always have fuel
            'has_upgrades': False, # No upgrades at gates
            'is_generated': True,
            'parent_location': location['id']  # Track which location this gate serves
        }
    
    async def _create_corridors(self, conn, routes: List[Dict], all_locations: List[Dict]) -> List[Dict]:
        """Create corridors with optimized batching and independent transaction management"""
        if not routes:
            return []
        
        # Handle transaction properly - commit if passed, otherwise start fresh
        if conn:
            self.db.commit_transaction(conn)
            conn = None
        
        print(f"🌉 Creating corridor network for {len(routes)} routes...")
        
        # Safety check: prevent excessive corridor creation
        current_corridor_count = self.db.execute_query("SELECT COUNT(*) FROM corridors", fetch='one')[0]
        if current_corridor_count > 1000:
            print(f"⚠️ WARNING: {current_corridor_count} corridors already exist. Skipping creation to prevent database overload.")
            return 0
        
        corridors_to_insert = []
        batch_size = 50  # Smaller batches
        corridors_created = 0
        
        for i, route in enumerate(routes):
            # Safety check: stop if we've created too many corridors
            if current_corridor_count + corridors_created > 800:
                print(f"⚠️ Stopping corridor creation at {corridors_created} new corridors to prevent overload.")
                break
                
            name = self._generate_corridor_name(route['from'], route['to'])
            loc1_id, loc2_id = route['from']['id'], route['to']['id']
            
            # Validate location IDs to prevent foreign key constraint violations
            if loc1_id <= 0 or loc2_id <= 0:
                print(f"⚠️ Skipping route {name}: invalid location IDs (from: {loc1_id}, to: {loc2_id})")
                continue
            dist = route['distance']
            fuel = max(10, int(dist * 0.8) + 5)
            danger = max(1, min(5, 2 + random.randint(-1, 2)))

            if route.get('has_gates', False) and 'origin_gate' in route and 'destination_gate' in route:
                # Gated route with 6 segments
                og_id = route['origin_gate']['id']
                dg_id = route['destination_gate']['id']
                
                # Validate gate IDs to prevent foreign key constraint violations
                if og_id <= 0 or dg_id <= 0:
                    print(f"⚠️ Skipping gated route {name}: invalid gate IDs (origin: {og_id}, dest: {dg_id})")
                    continue
                
                approach_time, main_time = self._calculate_gated_route_times(dist)
                gate_danger = max(1, danger - 1)
                
                # Reduced corridor creation: Only essential approach, main route, and arrival
                corridors_to_insert.extend([
                    (f"{name} Approach", loc1_id, og_id, approach_time, int(fuel*0.3), 1, True, True),
                    (name, og_id, dg_id, main_time, int(fuel*0.4), danger, True, True),
                    (f"{name} Arrival", dg_id, loc2_id, approach_time, int(fuel*0.3), 1, True, True),
                ])
                corridors_created += 3
            else:
                # Ungated route with 2 segments
                ungated_time = self._calculate_ungated_route_time(dist)
                ungated_danger = min(5, danger + 2)
                ungated_fuel = int(fuel * 0.7)
                corridors_to_insert.extend([
                    (f"{name} (Ungated)", loc1_id, loc2_id, ungated_time, ungated_fuel, ungated_danger, True, True),
                    (f"{name} Return (Ungated)", loc2_id, loc1_id, ungated_time, ungated_fuel, ungated_danger, True, True),
                ])
                corridors_created += 2
            
            # Insert in batches with micro-transactions
            if len(corridors_to_insert) >= batch_size:
                await self._insert_corridor_batch(corridors_to_insert)
                corridors_to_insert = []
                
                # Progress reporting
                progress = ((i + 1) / len(routes)) * 100
                if i % 25 == 0:
                    print(f"    🌉 Corridor progress: {progress:.0f}% ({corridors_created} segments)")
                
                # Yield control
                await asyncio.sleep(0.05)
        
        # Insert remaining corridors
        if corridors_to_insert:
            await self._insert_corridor_batch(corridors_to_insert)

        print(f"✅ Created {corridors_created} corridor segments")
        return corridors_to_insert

    async def _insert_corridor_batch(self, batch_data: List[tuple]):
        """Insert corridor batch in independent micro-transaction with retry logic"""
        if not batch_data:
            return
        
        # Retry logic for database lock issues    
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait a bit if this is a retry
                if attempt > 0:
                    await asyncio.sleep(0.3 * attempt)
                
                micro_conn = self.db.begin_transaction()
                break
            except RuntimeError as e:
                if "database lock" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Database lock in corridor creation, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    print(f"❌ Failed to acquire database lock for corridor creation: {e}")
                    return  # Skip this batch instead of crashing
        try:
            query = '''INSERT INTO corridors (name, origin_location, destination_location, 
                       travel_time, fuel_cost, danger_level, is_active, is_generated) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'''
            self.db.executemany_in_transaction(micro_conn, query, batch_data)
            self.db.commit_transaction(micro_conn)
        except Exception as e:
            self.db.rollback_transaction(micro_conn)
            print(f"❌ Error inserting corridor batch: {e}")
        finally:
            micro_conn = None

    def _calculate_gated_route_times(self, distance: float) -> Tuple[int, int]:
        """Calculate travel times for gated routes (approach + main corridor) - Target ~8min average, max 15min"""
        
        # Total time budget: 5-15 minutes (300-900 seconds) with ~8min average
        min_total_time = 5 * 60   # 5 minutes
        max_total_time = 15 * 60  # 15 minutes
        target_average = 8 * 60   # 8 minutes
        
        # Scale base time with distance but bias toward target average
        distance_factor = min(distance / 80.0, 1.0)  # Normalize to 80 units max
        base_total_time = target_average + (max_total_time - target_average) * (distance_factor * 0.6)
        
        # Add randomization (±20%) for variety
        variance = base_total_time * 0.2
        total_time = base_total_time + random.uniform(-variance, variance)
        
        # Clamp to 5-15 minute range
        total_time = max(min_total_time, min(max_total_time, int(total_time)))
        
        # Split into approach (30%) and main corridor (70%)
        approach_time = int(total_time * 0.3)
        main_time = total_time - approach_time
        
        # Ensure minimums
        approach_time = min(300, approach_time)  # At least 5 minutes
        main_time = min(480 , main_time)  # At least 8 minutes
        
        return approach_time, main_time

    def _calculate_ungated_route_time(self, distance: float) -> int:
        """Calculate travel time for ungated routes - Target ~6min average, max 15min (faster but riskier than gated)"""
        
        min_time = 3 * 60   # 3 minutes
        max_time = 15 * 60  # 15 minutes (global max)
        target_average = 6 * 60  # 6 minutes
        
        # Scale with distance but bias toward target average
        distance_factor = min(distance / 80.0, 1.0)  # Normalize to 80 units max
        base_time = target_average + (max_time - target_average) * (distance_factor * 0.5)
        
        # Add randomization (±25% for ungated unpredictability)
        variance = base_time * 0.25
        ungated_time = base_time + random.uniform(-variance, variance)
        
        # Clamp to 3-15 minute range
        ungated_time = max(min_time, min(max_time, int(ungated_time)))
        
        return int(ungated_time)
    
    def _create_corridor_segment(self, name: str, origin_id: int, dest_id: int, 
                               travel_time: int, fuel_cost: int, danger_level: int, has_gate: bool = True) -> Dict:
        """Create a single corridor segment with proper corridor type classification"""
        
        # Determine corridor type based on name and connected locations
        corridor_type = self._determine_corridor_type(origin_id, dest_id, name)
        
        # Save to database with corridor_type
        self.db.execute_query(
            '''INSERT INTO corridors 
               (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, corridor_type, is_generated)
               VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)''',
            (name, origin_id, dest_id, travel_time, fuel_cost, danger_level, corridor_type)
        )
        
        return {
            'name': name,
            'origin_id': origin_id,
            'destination_id': dest_id,
            'travel_time': travel_time,
            'fuel_cost': fuel_cost,
            'danger_level': danger_level,
            'has_gate': has_gate
        }
    
    def _generate_corridor_name(self, from_loc: Dict, to_loc: Dict) -> str:
        """Generate a lore-appropriate corridor name"""
        # Ensure we have the required fields
        from_name = from_loc.get('name', 'Unknown')
        to_name = to_loc.get('name', 'Unknown')
        from_system = from_loc.get('system_name', 'Unknown')
        to_system = to_loc.get('system_name', 'Unknown')
        
        # Generate shorter, more predictable names
        corridor_suffix = random.choice(self.corridor_names)
        
        base_names = [
            f"{from_name}-{to_name} {corridor_suffix}",
            f"{from_system} {corridor_suffix}",
            f"{to_system} {corridor_suffix}",
            f"{random.choice(['Trans', 'Inter', 'Cross'])}-{random.choice([from_system, to_system])} {corridor_suffix}"
        ]
        
        # Pick the shortest name that's still reasonable
        name = min(base_names, key=len)
        
        # Ensure name isn't too long
        if len(name) > 80:  # Leave room for "(Dormant)" suffix
            name = name[:77] + "..."
        
        return name
    
    def _save_location_to_db(self, conn, location: Dict[str, Any]) -> int:
        """Saves a single location within a transaction and returns its new ID."""
        print(f"🔧 DEBUG: _save_location_to_db called for {location.get('name', 'Unknown')}")
        query = '''INSERT INTO locations 
                   (name, location_type, description, wealth_level, population,
                    x_coordinate, y_coordinate, system_name, established_date, has_jobs, has_shops, has_medical, 
                    has_repairs, has_fuel, has_upgrades, has_black_market, is_generated, is_derelict, has_shipyard) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING location_id'''
        params = (
            location['name'], location['type'], location['description'], 
            location['wealth_level'], location['population'], location['x_coordinate'], 
            location['y_coordinate'], location['system_name'], location.get('established_date'),
            location['has_jobs'], location['has_shops'], location['has_medical'], 
            location['has_repairs'], location['has_fuel'], location['has_upgrades'],
            location.get('has_black_market', False), location['is_generated'], 
            location.get('is_derelict', False), location.get('has_shipyard', False)
        )
        print(f"🔧 DEBUG: Params prepared for {location.get('name')}: type={location['type']}")
        print(f"🔧 DEBUG: About to execute INSERT for {location.get('name')}")
        result = self.db.execute_in_transaction(conn, query, params, fetch='one')
        print(f"🔧 DEBUG: INSERT completed for {location.get('name')}, got result: {result}")
        
        # Extract the location_id from the returned tuple
        location_id = result[0] if result and len(result) > 0 else None
        print(f"🔧 DEBUG: Extracted location_id: {location_id}")
        
        # Validate the returned ID
        if location_id is None or location_id <= 0:
            error_msg = f"❌ Invalid location ID returned from database: {location_id} for location {location.get('name')}"
            print(error_msg)
            raise ValueError(error_msg)
            
        return location_id
    
    def _generate_unique_name(self, loc_type: str, used_names: set) -> str:
        """Generate a unique location name"""
        
        attempts = 0
        while attempts < 50:
            if loc_type == 'space_station':
                if random.random() < 0.7:
                    name = f"{random.choice(self.location_names)} Station"
                else:
                    name = f"{random.choice(self.location_prefixes)} {random.choice(self.location_names)}"
            elif loc_type == 'outpost':
                name = f"{random.choice(self.location_names)} Outpost"
            else:  # colony
                if random.random() < 0.5:
                    name = f"{random.choice(self.location_prefixes)} {random.choice(self.location_names)}"
                else:
                    name = random.choice(self.location_names)
            
            if name not in used_names:
                return name
            attempts += 1
        
        # Fallback with numbers
        base_name = random.choice(self.location_names)
        counter = 1
        while f"{base_name} {counter}" in used_names:
            counter += 1
        return f"{base_name} {counter}"
    
    def _generate_unique_system(self, used_systems: set) -> str:
        """Generate a unique system name"""
        
        available_systems = [s for s in self.system_names if s not in used_systems]
        if available_systems:
            return random.choice(available_systems)
        
        # Generate numbered systems if we run out
        counter = 1
        while f"System-{counter:03d}" in used_systems:
            counter += 1
        return f"System-{counter:03d}"
    
    def _find_nearby_locations(self, location: Dict, candidates: List[Dict], max_distance: float) -> List[Dict]:
        """Find locations within max_distance, sorted by proximity"""
        
        nearby = []
        for candidate in candidates:
            if candidate['id'] != location['id']:  # Don't include self
                distance = self._calculate_distance(location, candidate)
                if distance <= max_distance:
                    nearby.append(candidate)
        
        # Sort by distance
        nearby.sort(key=lambda loc: self._calculate_distance(location, loc))
        return nearby
    
    def _calculate_distance(self, loc1: Dict, loc2: Dict) -> float:
        """Calculate distance between two locations"""
        dx = loc1['x_coordinate'] - loc2['x_coordinate']
        dy = loc1['y_coordinate'] - loc2['y_coordinate']
        return math.sqrt(dx * dx + dy * dy)
    
    # Visual map generation with updated gate display
    @galaxy_group.command(name="visual_map", description="Generate a visual map of the galaxy")
    @app_commands.describe(
        map_style="Style of the visual map",
        show_labels="Whether to show location names",
        show_routes="Whether to show corridor routes",  # NEW PARAMETER
        highlight_player="Highlight a specific player's location"
    )
    @app_commands.choices(map_style=[
        app_commands.Choice(name="Standard", value="standard"),
        app_commands.Choice(name="Infrastructure", value="infrastructure"), 
        app_commands.Choice(name="Wealth", value="wealth"),
        app_commands.Choice(name="Connections", value="connections"),
        app_commands.Choice(name="Danger", value="danger")
    ])
    async def visual_map(self, interaction: discord.Interaction, 
                        map_style: str = "standard", 
                        show_labels: bool = False,
                        show_routes: bool = True,  # NEW PARAMETER with default True
                        highlight_player: discord.Member = None):
        
        await interaction.response.defer()
        
        try:
            # Pass the new parameter to map generation
            map_buffer = await self._generate_visual_map(map_style, show_labels, show_routes, highlight_player)
            
            if map_buffer is None:
                await interaction.followup.send("No locations found! Generate a galaxy first with `/galaxy generate`.")
                return
            
            map_file = discord.File(map_buffer, filename=f"galaxy_map_{map_style}.png")
            
            embed = discord.Embed(
                title=f"🌌 Galaxy Map - {map_style.title()} View",
                description=self._get_map_description(map_style),
                color=0x4169E1
            )
            
            legend_text = self._get_legend_text(map_style, show_routes)  # Updated to consider routes
            if legend_text:
                embed.add_field(name="Legend", value=f"```\n{legend_text}\n```", inline=False)
            
            stats = await self._get_galaxy_stats()
            if stats:
                embed.add_field(name="Galaxy Statistics", value=stats, inline=True)
            
            embed.set_image(url="attachment://galaxy_map_{}.png".format(map_style))
            
            await interaction.followup.send(embed=embed, file=map_file)
            
        except Exception as e:
            import traceback
            print(f"Visual map generation error: {traceback.format_exc()}")
            await interaction.followup.send(f"Error generating visual map: {str(e)}\nPlease check that the galaxy has been generated and try again.")
    
    async def _generate_visual_map(self, map_style: str, show_labels: bool, show_routes: bool, highlight_player: discord.Member = None) -> io.BytesIO:
        """Generate visual map with enhanced theme matching landing page aesthetic"""
        
        # Fetch locations
        locations = self.db.execute_query(
            "SELECT location_id, name, location_type, x_coordinate, y_coordinate, wealth_level FROM locations",
            fetch='all'
        )
        if not locations:
            return None
        
        # Fetch corridors only if show_routes is True
        corridors = []
        if show_routes:
            corridors = self.db.execute_query(
                '''SELECT c.origin_location, c.destination_location, c.danger_level,
                          ol.x_coordinate as ox, ol.y_coordinate as oy,
                          dl.x_coordinate as dx, dl.y_coordinate as dy, ol.location_type as origin_type,
                          c.name as corridor_name
                   FROM corridors c
                   JOIN locations ol ON c.origin_location = ol.location_id
                   JOIN locations dl ON c.destination_location = dl.location_id
                   WHERE c.is_active = true''',
                fetch='all'
            )
        
        # Get galaxy theme based on galaxy name (matches web map)
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        galaxy_info = time_system.get_galaxy_info()
        galaxy_name = galaxy_info[0] if galaxy_info else "Unknown Galaxy"

        # CHANGED: Add debugging and ensure proper theme distribution
        import hashlib
        # Use full hash for better distribution
        theme_hash = hashlib.md5(f"{galaxy_name}".encode()).hexdigest()
        # Use more of the hash for better randomness
        theme_value = int(theme_hash[:12], 16)
        theme_index = theme_value % 5
        themes = ['blue', 'amber', 'green', 'red', 'purple']
        selected_theme = themes[theme_index]

        # Debug print to verify theme selection
        print(f"🎨 Galaxy '{galaxy_name}' using theme: {selected_theme} (index: {theme_index})")
        
        # Define theme colors matching landing page
        theme_colors = {
            'blue': {
                'primary': '#00ffff',
                'secondary': '#00cccc',
                'accent': '#0088cc',
                'glow': '#00ffff',
                'bg_primary': '#000408',
                'bg_secondary': '#0a0f1a',
                'text': '#e0ffff'
            },
            'amber': {
                'primary': '#ffaa00',
                'secondary': '#cc8800',
                'accent': '#ff6600',
                'glow': '#ffaa00',
                'bg_primary': '#080400',
                'bg_secondary': '#1a0f0a',
                'text': '#fff0e0'
            },
            'green': {
                'primary': '#00ff88',
                'secondary': '#00cc66',
                'accent': '#00aa44',
                'glow': '#00ff88',
                'bg_primary': '#000804',
                'bg_secondary': '#0a1a0f',
                'text': '#e0ffe8'
            },
            'red': {
                'primary': '#ff4444',
                'secondary': '#cc2222',
                'accent': '#aa0000',
                'glow': '#ff4444',
                'bg_primary': '#080004',
                'bg_secondary': '#1a0a0a',
                'text': '#ffe0e0'
            },
            'purple': {
                'primary': '#cc66ff',
                'secondary': '#9933cc',
                'accent': '#6600aa',
                'glow': '#cc66ff',
                'bg_primary': '#040008',
                'bg_secondary': '#0f0a1a',
                'text': '#f0e0ff'
            }
        }
        
        theme = theme_colors[selected_theme]
        
        # Look up the player's current location
        player_location = None
        player_coords = None
        if highlight_player:
            result = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = %s",
                (highlight_player.id,), fetch='one'
            )
            if result:
                player_location = result[0]
                loc_data = self.db.execute_query(
                    "SELECT x_coordinate, y_coordinate FROM locations WHERE location_id = %s",
                    (player_location,), fetch='one'
                )
                if loc_data:
                    player_coords = (loc_data[0], loc_data[1])
        
        # Determine zoom level and focus
        zoom_level = "galaxy"
        focus_center = None
        focus_radius = 50
        
        if player_coords:
            zoom_level = "regional"
            focus_center = player_coords
            focus_radius = 40
        
        # Filter visible locations based on zoom
        visible_locations = []
        if zoom_level == "regional" and focus_center:
            fx, fy = focus_center
            for loc in locations:
                lx, ly = loc[3], loc[4]
                if abs(lx - fx) <= focus_radius and abs(ly - fy) <= focus_radius:
                    visible_locations.append(loc)
        else:
            visible_locations = locations
        
        # Filter visible corridors
        visible_location_ids = {loc[0] for loc in visible_locations}
        visible_corridors = []
        if corridors:
            for corridor in corridors:
                origin_id, dest_id = corridor[0], corridor[1]
                if origin_id in visible_location_ids and dest_id in visible_location_ids:
                    visible_corridors.append(corridor)
        
        # Create figure with dark theme
        fig = plt.figure(figsize=(14, 10), facecolor=theme['bg_primary'])
        ax = fig.add_subplot(111, facecolor=theme['bg_primary'])
        
        # Draw enhanced map elements
        if show_routes and corridors:
            await self._draw_enhanced_corridors(ax, visible_corridors, map_style, theme, zoom_level) 
        await self._draw_enhanced_locations(ax, visible_locations, map_style, theme, player_location, zoom_level)
        await self._draw_enhanced_locations(ax, visible_locations, map_style, theme, player_location, zoom_level)
        
        if show_labels:
            await self._add_enhanced_labels(ax, visible_locations, theme, zoom_level, player_location)
        
        # Add enhanced UI elements
        await self._add_enhanced_ui_elements(ax, theme, map_style, zoom_level, galaxy_name, player_location)
        
        # Style the plot
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Set view bounds
        if zoom_level == "regional" and focus_center:
            fx, fy = focus_center
            margin = focus_radius * 1.2
            ax.set_xlim(fx - margin, fx + margin)
            ax.set_ylim(fy - margin, fy + margin)
        else:
            if visible_locations:
                x_coordinates = [loc[3] for loc in visible_locations]
                y_coordinates = [loc[4] for loc in visible_locations]
                x_range = max(x_coordinates) - min(x_coordinates)
                y_range = max(y_coordinates) - min(y_coordinates)
                padding = max(x_range, y_range) * 0.1
                
                ax.set_xlim(min(x_coordinates) - padding, max(x_coordinates) + padding)
                ax.set_ylim(min(y_coordinates) - padding, max(y_coordinates) + padding)
        
        # Save to buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                    facecolor=theme['bg_primary'], edgecolor='none')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    async def _draw_enhanced_space_background(self, ax, theme, zoom_level, focus_center, focus_radius):
        """Draw enhanced space background matching landing page aesthetic"""
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Create gradient background
        from matplotlib.patches import Rectangle
        from matplotlib.collections import PatchCollection
        
        # Add subtle gradient overlay
        gradient = Rectangle((xlim[0], ylim[0]), xlim[1]-xlim[0], ylim[1]-ylim[0])
        gradient.set_facecolor(theme['bg_secondary'])
        gradient.set_alpha(0.3)
        ax.add_patch(gradient)
        
        # Enhanced starfield
        num_stars = 300 if zoom_level == "galaxy" else 150
        star_x = np.random.uniform(xlim[0], xlim[1], num_stars)
        star_y = np.random.uniform(ylim[0], ylim[1], num_stars)
        
        # Varying star sizes and brightness
        star_sizes = np.random.exponential(1.5, num_stars)
        star_alphas = np.random.uniform(0.2, 0.8, num_stars)
        
        for i in range(num_stars):
            ax.scatter(star_x[i], star_y[i], c=theme['text'], 
                      s=star_sizes[i], alpha=star_alphas[i], 
                      marker='*', zorder=0)
        
        # Add nebula clouds with theme colors
        nebula_count = 5 if zoom_level == "galaxy" else 3
        for _ in range(nebula_count):
            center_x = random.uniform(xlim[0], xlim[1])
            center_y = random.uniform(ylim[0], ylim[1])
            width = random.uniform(30, 60)
            height = random.uniform(25, 50)
            
            nebula = patches.Ellipse((center_x, center_y), width, height,
                                   alpha=0.05, facecolor=theme['primary'],
                                   zorder=0)
            ax.add_patch(nebula)
        
        # Add grid for terminal feel
        if zoom_level == "regional":
            ax.grid(True, alpha=0.1, color=theme['primary'], 
                    linestyle=':', linewidth=0.5)

    async def _draw_enhanced_corridors(self, ax, corridors, map_style, theme, zoom_level):
        """Draw corridors with enhanced visual style and clear type distinction"""
        if not corridors:
            return
        
        # Group corridors by type with more detailed categorization
        corridor_groups = {
            'local_space': [],      # Approach/Arrival segments
            'gated_main': [],       # Main gated corridors
            'ungated': []           # Dangerous ungated routes
        }
        
        for corridor in corridors:
            origin_id, dest_id, danger, ox, oy, dx, dy, origin_type, corridor_name = corridor
            
            if corridor_name:
                name_lower = corridor_name.lower()
                # Categorize by corridor name patterns
                if any(term in name_lower for term in ['approach', 'arrival', 'departure']):
                    corridor_groups['local_space'].append(corridor)
                elif 'ungated' in name_lower:
                    corridor_groups['ungated'].append(corridor)
                else:
                    # Check if it's between gates (main gated corridor)
                    origin_is_gate = self.db.execute_query(
                        "SELECT location_type FROM locations WHERE location_id = %s",
                        (origin_id,), fetch='one'
                    )
                    dest_is_gate = self.db.execute_query(
                        "SELECT location_type FROM locations WHERE location_id = %s",
                        (dest_id,), fetch='one'
                    )
                    
                    if origin_is_gate and dest_is_gate and origin_is_gate[0] == 'gate' and dest_is_gate[0] == 'gate':
                        corridor_groups['gated_main'].append(corridor)
                    else:
                        corridor_groups['local_space'].append(corridor)
            else:
                corridor_groups['ungated'].append(corridor)
        
        # Draw corridors in specific order for proper layering
        # Order: local_space first (bottom), then gated_main, then ungated (top)
        for corridor_type, corridor_list in [('local_space', corridor_groups['local_space']),
                                             ('gated_main', corridor_groups['gated_main']),
                                             ('ungated', corridor_groups['ungated'])]:
            for corridor in corridor_list:
                origin_id, dest_id, danger, ox, oy, dx, dy, origin_type, corridor_name = corridor
                
                if corridor_type == 'local_space':
                    # Local space travel - visible dotted lines with subtle glow
                    # Use a lighter color for better visibility against dark background
                    local_color = theme['primary'] if theme['primary'] != theme['secondary'] else theme['text']
                    
                    # Draw subtle glow for better visibility
                    ax.plot([ox, dx], [oy, dy], 
                           color=local_color, 
                           linewidth=3.0,
                           linestyle=':',
                           alpha=0.2,
                           zorder=1)
                    # Main dotted line
                    ax.plot([ox, dx], [oy, dy], 
                           color=local_color, 
                           linewidth=1.5,
                           linestyle=':',
                           alpha=0.7,
                           zorder=1,
                           label='Local Space' if corridor == corridor_list[0] else "")
                           
                elif corridor_type == 'gated_main':
                    # Main gated corridors - prominent solid lines with glow
                    # Draw glow effect
                    ax.plot([ox, dx], [oy, dy], 
                           color=theme['glow'], 
                           linewidth=5.0,
                           alpha=0.15,
                           zorder=2)
                    # Draw main line
                    ax.plot([ox, dx], [oy, dy], 
                           color=theme['primary'], 
                           linewidth=2.0,
                           linestyle='-',
                           alpha=0.8,
                           zorder=3,
                           label='Gated Corridor' if corridor == corridor_list[0] else "")
                           
                else:  # ungated
                    # Ungated corridors - dashed lines colored by danger
                    danger_colors = {
                        1: '#00ff00',
                        2: '#88ff00', 
                        3: '#ffaa00',
                        4: '#ff6600',
                        5: '#ff3333'
                    }
                    color = danger_colors.get(danger, '#ff6600')
                    
                    # More prominent dashing for dangerous routes
                    if danger >= 4:
                        dash_pattern = (5, 5)  # Longer dashes for very dangerous
                    else:
                        dash_pattern = (8, 4)  # Standard dashes
                    
                    ax.plot([ox, dx], [oy, dy], 
                           color=color, 
                           linewidth=1.5,
                           linestyle='--',
                           dashes=dash_pattern,
                           alpha=0.7,
                           zorder=4,
                           label=f'Ungated (Danger {danger})' if corridor == corridor_list[0] else "")
                           
    async def _draw_enhanced_locations(self, ax, locations, map_style, theme, player_location=None, zoom_level="galaxy"):
        """Draw locations with enhanced cyberpunk aesthetic - CORRECTED MARKERS"""
        
        # Enhanced location styles - FIXED TO MATCH WEB MAP
        location_styles = {
            'colony': {
                'marker': 'o',  # Circle - CORRECT
                'base_size': 200 if zoom_level == "regional" else 150,
                'icon': '🏙️'
            },
            'space_station': {
                'marker': '^',  # CHANGED FROM 's' TO '^' (Triangle)
                'base_size': 250 if zoom_level == "regional" else 200,
                'icon': '🛸'
            },
            'outpost': {
                'marker': 's',  # CHANGED FROM '^' TO 's' (Square)
                'base_size': 150 if zoom_level == "regional" else 100,
                'icon': '📡'
            },
            'gate': {
                'marker': 'D',  # Diamond - CORRECT
                'base_size': 100 if zoom_level == "regional" else 60,
                'icon': '🌀'
            }
        }
        
        # Draw locations with glow effects
        for loc in locations:
            loc_id, name, loc_type, x, y, wealth = loc
            style = location_styles.get(loc_type, location_styles['outpost'])
            
            # Determine color based on map style
            if map_style == 'wealth':
                wealth_colors = {
                    range(1, 5): '#ff4444',
                    range(5, 8): '#ffaa00',
                    range(8, 11): '#00ff88'
                }
                color = theme['secondary']
                for wealth_range, wealth_color in wealth_colors.items():
                    if wealth in wealth_range:
                        color = wealth_color
                        break
            else:
                # CHANGED: Make gates use a more subtle color
                if loc_type == 'gate':
                    color = theme['accent']  # More subtle than primary
                else:
                    color = theme['primary']
            
            # Special highlighting for player location
            if player_location and loc_id == player_location:
                # Draw pulse effect
                for i in range(3):
                    ax.scatter(x, y, 
                              s=style['base_size'] * (2 - i*0.5),
                              c=theme['glow'],
                              marker=style['marker'],
                              alpha=0.1 * (3-i),
                              zorder=3)
            
            # CHANGED: Reduced glow effect for gates
            if loc_type != 'gate':
                # Draw glow effect for non-gates
                ax.scatter(x, y, 
                          s=style['base_size'] * 2,
                          c=color,
                          marker=style['marker'],
                          alpha=0.2,
                          zorder=4)
            
            # Draw main location
            # CHANGED: Gates are more transparent
            alpha = 0.6 if loc_type == 'gate' else 0.9
            
            ax.scatter(x, y, 
                      s=style['base_size'],
                      c=color,
                      marker=style['marker'],
                      edgecolor=theme['text'],
                      linewidth=1 if loc_type != 'gate' else 0.5,
                      alpha=alpha,
                      zorder=5)

    async def _add_enhanced_labels(self, ax, locations, theme, zoom_level, player_location):
        """Add labels with enhanced readability and reduced gate clutter"""
        
        # Separate location types
        gates = []
        stations = []
        colonies = []
        outposts = []
        
        for loc in locations:
            loc_id, name, loc_type, x, y, wealth = loc
            if loc_type == 'gate':
                gates.append(loc)
            elif loc_type == 'space_station':
                stations.append(loc)
            elif loc_type == 'colony':
                colonies.append(loc)
            else:
                outposts.append(loc)
        
        # CHANGED: Only label a subset of gates to reduce clutter
        # For gates, only label the most important ones (wealthy or well-connected)
        important_gates = []
        if gates:
            # Get connectivity data for gates
            gate_connectivity = {}
            for gate in gates:
                connections = self.db.execute_query(
                    "SELECT COUNT(*) FROM corridors WHERE origin_location = %s OR destination_location = %s",
                    (gate[0], gate[0]), fetch='one'
                )[0]
                gate_connectivity[gate[0]] = connections
            
            # Sort gates by connectivity and wealth
            gates_sorted = sorted(gates, 
                                key=lambda g: (gate_connectivity.get(g[0], 0), g[5]), 
                                reverse=True)
            
            # Only label top 20% of gates in galaxy view, 40% in regional view
            if zoom_level == "galaxy":
                max_gate_labels = max(1, len(gates_sorted) // 5)  # 20%
            else:
                max_gate_labels = max(2, len(gates_sorted) * 2 // 5)  # 40%
            
            important_gates = gates_sorted[:max_gate_labels]
        
        # CHANGED: Label order now prioritizes major locations over gates
        # Order: stations first, then colonies, important gates, and finally outposts
        labeled_locations = stations + colonies + important_gates
        
        # Only label outposts in regional view
        if zoom_level == "regional":
            labeled_locations += outposts
        
        # Add labels with backdrop
        labeled_count = 0
        max_labels = 30 if zoom_level == "regional" else 20  # Limit total labels
        
        for loc in labeled_locations:
            if labeled_count >= max_labels:
                break
                
            loc_id, name, loc_type, x, y, wealth = loc
            
            # Skip very long names in galaxy view
            if zoom_level == "galaxy" and len(name) > 20:
                name = name[:17] + "..."
            
            # Special handling for gate names - shorten them
            if loc_type == 'gate' and zoom_level == "galaxy":
                # Extract just the essential part of gate name
                # e.g., "Earth-Delta Gate" -> "Delta Gate"
                parts = name.split('-')
                if len(parts) > 1:
                    name = parts[-1].strip()
                if len(name) > 15:
                    name = name[:12] + "..."
            
            # Position label based on location type
            offset_y = 8 if loc_type in ['colony', 'space_station'] else 6
            
            # Add text with background box
            bbox_props = dict(boxstyle="round,pad=0.3", 
                             facecolor=theme['bg_primary'], 
                             edgecolor=theme['primary'],
                             alpha=0.8,
                             linewidth=0.5)
            
            # Make gate labels smaller and less prominent
            if loc_type == 'gate':
                fontsize = 7 if zoom_level == "regional" else 6
                alpha = 0.6
            else:
                fontsize = 9 if zoom_level == "regional" else 8
                alpha = 0.8
            
            ax.text(x, y + offset_y, name,
                   fontsize=fontsize,
                   color=theme['text'],
                   ha='center',
                   va='bottom',
                   bbox=bbox_props,
                   alpha=alpha,
                   zorder=10)
            
            labeled_count += 1

    async def _add_enhanced_ui_elements(self, ax, theme, map_style, zoom_level, galaxy_name, player_location):
        """Add UI elements matching the terminal aesthetic"""
        
        # Add galaxy name and timestamp
        from datetime import datetime
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        current_time = time_system.calculate_current_ingame_time()
        formatted_time = time_system.format_ingame_datetime(current_time) if current_time else "Unknown"
        
        # Terminal-style header
        header_text = f"[NAVIGATION SYSTEM v3.14]\n{galaxy_name.upper()} | {formatted_time}"
        ax.text(0.02, 0.98, header_text,
               transform=ax.transAxes,
               fontsize=10,
               color=theme['primary'],
               va='top',
               ha='left',
               family='monospace',
               bbox=dict(boxstyle="round,pad=0.5", 
                        facecolor=theme['bg_secondary'], 
                        edgecolor=theme['primary'],
                        alpha=0.8))
        
        # Enhanced legend
        legend_items = []
        if map_style == 'standard':
            legend_items = [
                "LOCATION MARKERS:",
                "◆ Transit Gates",
                "■ Space Stations", 
                "● Colonies",
                "▲ Outposts"
            ]
        elif map_style == 'infrastructure':
            legend_items = [
                "INFRASTRUCTURE:",
                "━━ Gated Routes",
                "┅┅ Standard Routes",
                "••• Approach Lanes",
                "◆ Active Gates"
            ]
        elif map_style == 'wealth':
            legend_items = [
                "ECONOMIC STATUS:",
                "● Wealthy (8-10)",
                "● Moderate (5-7)",
                "● Poor (1-4)"
            ]
        elif map_style == 'danger':
            legend_items = [
                "ROUTE DANGER:",
                "━━ Safe (1-2)",
                "┅┅ Moderate (3)",
                "••• Dangerous (4-5)"
            ]
        
        if legend_items:
            legend_text = '\n'.join(legend_items)
            ax.text(0.02, 0.82, legend_text,
                   transform=ax.transAxes,
                   fontsize=8,
                   color=theme['text'],
                   va='top',
                   ha='left',
                   family='monospace',
                   bbox=dict(boxstyle="round,pad=0.5", 
                            facecolor=theme['bg_secondary'], 
                            edgecolor=theme['secondary'],
                            alpha=0.8))
        
        # Status bar at bottom
        status_items = []
        status_items.append(f"View: {map_style.upper()}")
        status_items.append(f"Scale: {zoom_level.upper()}")
        if player_location:
            status_items.append(f"Tracking: ACTIVE")
        
        status_text = " | ".join(status_items)
        ax.text(0.98, 0.02, status_text,
               transform=ax.transAxes,
               fontsize=8,
               color=theme['secondary'],
               va='bottom',
               ha='right',
               family='monospace')

    async def _draw_space_background(self, ax, zoom_level: str, focus_center: tuple = None, focus_radius: float = None):
        """Draw enhanced space background with context-aware details"""
        
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Determine star density based on zoom level
        if zoom_level == "regional":
            star_density = 200  # More stars for regional view
            nebula_count = 2
            nebula_size_range = (8, 20)
        else:
            star_density = 150  # Fewer stars for galaxy view
            nebula_count = 4
            nebula_size_range = (20, 50)
        
        # Enhanced star field
        star_x = np.random.uniform(xlim[0], xlim[1], star_density)
        star_y = np.random.uniform(ylim[0], ylim[1], star_density)
        
        # Variable star sizes and colors
        star_sizes = np.random.exponential(1.5, star_density)
        star_colors = np.random.choice(['white', '#ffffaa', '#aaaaff', '#ffaaaa'], star_density, p=[0.6, 0.2, 0.15, 0.05])
        star_alphas = np.random.uniform(0.2, 0.8, star_density)
        
        for i in range(star_density):
            ax.scatter(star_x[i], star_y[i], c=star_colors[i], s=star_sizes[i], 
                      alpha=star_alphas[i], zorder=0)
        
        # Enhanced nebulae with varied colors
        nebula_colors = ['#4B0082', '#483D8B', '#2F4F4F', '#8B4513', '#556B2F']
        
        for _ in range(nebula_count):
            center_x = random.uniform(xlim[0], xlim[1])
            center_y = random.uniform(ylim[0], ylim[1])
            width = random.uniform(*nebula_size_range)
            height = random.uniform(*nebula_size_range)
            
            nebula = patches.Ellipse((center_x, center_y), width, height,
                                   alpha=random.uniform(0.15, 0.25), 
                                   facecolor=random.choice(nebula_colors),
                                   zorder=0)
            ax.add_patch(nebula)
        
        # Add grid for regional view
        if zoom_level == "regional" and focus_center:
            ax.grid(True, alpha=0.15, color='cyan', linestyle=':', linewidth=0.5)
    async def _draw_locations_enhanced(self, ax, locations, map_style, player_location=None, zoom_level="galaxy"):
        """Draw locations with enhanced visibility and context-aware sizing"""
        
        # Enhanced location styles with zoom-aware sizing
        base_sizes = {
            'colony': 120 if zoom_level == "regional" else 100,
            'space_station': 160 if zoom_level == "regional" else 140,
            'outpost': 90 if zoom_level == "regional" else 70,
            'gate': 60 if zoom_level == "regional" else 40
        }
        
        location_styles = {
            'colony': {'marker': 'o', 'base_color': '#ff6600', 'size': base_sizes['colony']},
            'space_station': {'marker': 's', 'base_color': '#00aaff', 'size': base_sizes['space_station']},
            'outpost': {'marker': '^', 'base_color': '#888888', 'size': base_sizes['outpost']},
            'gate': {'marker': 'D', 'base_color': '#ffdd00', 'size': base_sizes['gate']}
        }
        
        # Separate locations by type for proper layering
        location_layers = {
            'major': [loc for loc in locations if loc[2] in ['colony', 'space_station']],
            'minor': [loc for loc in locations if loc[2] == 'outpost'],
            'infrastructure': [loc for loc in locations if loc[2] == 'gate']
        }
        
        # Draw in layers: infrastructure -> minor -> major -> player
        for layer_name, location_list in location_layers.items():
            for location in location_list:
                loc_id, name, loc_type, x, y, wealth = location
                style = location_styles.get(loc_type, location_styles['colony'])
                
                # Determine color and size based on map style
                color, size, alpha = await self._get_location_appearance(
                    loc_id, loc_type, wealth, map_style, style, zoom_level
                )
                
                # Enhanced glow effect for important locations
                if wealth >= 8 or loc_type == 'space_station':
                    glow_color = color if isinstance(color, str) else '#ffffff'
                    ax.scatter(x, y, c=glow_color, marker=style['marker'], 
                              s=size*1.5, alpha=0.3, zorder=2)
                
                # Main location marker
                ax.scatter(x, y, c=color, marker=style['marker'], s=size, 
                          edgecolors='white', linewidth=1.5, alpha=alpha, zorder=3)
                
                # Special indicators
                if wealth >= 9:
                    # Wealth indicator
                    ax.scatter(x, y+2, c='gold', marker='*', s=20, zorder=4)
                
                # Black market indicator (if applicable)
                has_black_market = self.db.execute_query(
                    "SELECT has_black_market FROM locations WHERE location_id = %s",
                    (loc_id,), fetch='one'
                )
                if has_black_market and has_black_market[0]:
                    ax.scatter(x-2, y-2, c='red', marker='o', s=15, alpha=0.7, zorder=4)
        
        # Draw player location with enhanced highlighting
        if player_location:
            for location in locations:
                loc_id, name, loc_type, x, y, wealth = location
                if loc_id == player_location:
                    # Multiple ring system for better visibility
                    rings = [
                        {'radius': 25, 'color': 'yellow', 'width': 4, 'alpha': 1.0},
                        {'radius': 20, 'color': 'white', 'width': 3, 'alpha': 0.9},
                        {'radius': 15, 'color': 'red', 'width': 2, 'alpha': 0.8}
                    ]
                    
                    for ring in rings:
                        circle = plt.Circle((x, y), ring['radius'], fill=False, 
                                          color=ring['color'], linewidth=ring['width'], 
                                          alpha=ring['alpha'], zorder=5)
                        ax.add_patch(circle)
                    
                    # Central star indicator
                    ax.scatter(x, y, c='yellow', marker='*', s=200, 
                              edgecolors='red', linewidth=2, alpha=1.0, zorder=6)
                    break

    async def _get_location_appearance(self, loc_id: int, loc_type: str, wealth: int, 
                                     map_style: str, style: dict, zoom_level: str):
        """Get enhanced appearance based on map style and context"""
        
        base_color = style['base_color']
        base_size = style['size']
        alpha = 1.0
        
        if map_style == 'wealth':
            # Enhanced wealth visualization
            wealth_ratio = wealth / 10.0
            color = plt.cm.RdYlGn(wealth_ratio)
            size = base_size + (wealth * 8)
            
        elif map_style == 'infrastructure':
            if loc_type == 'gate':
                color = '#ffff00'  # Bright yellow for gates
                size = base_size + 30
            elif loc_type == 'space_station':
                color = '#00ffff'  # Cyan for stations
                size = base_size + 20
            else:
                color = base_color
                size = base_size
                alpha = 0.7
                
        elif map_style == 'connections':
            # Color and size based on connectivity
            connections = self.db.execute_query(
                "SELECT COUNT(*) FROM corridors WHERE origin_location = %s OR destination_location = %s",
                (loc_id, loc_id), fetch='one'
            )[0]
            
            connection_ratio = min(connections / 8.0, 1.0)
            color = plt.cm.plasma(connection_ratio)
            size = base_size + (connections * 10)
            
        elif map_style == 'danger':
            # Color based on nearby corridor danger
            avg_danger = self.db.execute_query(
                "SELECT AVG(danger_level) FROM corridors WHERE origin_location = %s",
                (loc_id,), fetch='one'
            )[0] or 1
            
            danger_ratio = (avg_danger - 1) / 4.0  # Normalize 1-5 to 0-1
            color = plt.cm.Reds(0.3 + danger_ratio * 0.7)
            size = base_size
            
        else:  # standard
            color = base_color
            size = base_size
        
        return color, size, alpha
    
    async def _draw_corridors_enhanced(self, ax, corridors, map_style, zoom_level="galaxy"):
        """Draw corridors with enhanced visual distinction and clarity"""
        
        # Base styling
        line_width_base = 1.5 if zoom_level == "regional" else 1.0
        alpha_base = 0.6 if zoom_level == "regional" else 0.4
        
        # Group corridors by type for better layering
        corridor_groups = {
            'approach': [],
            'gated': [],
            'ungated': []
        }
        
        for corridor in corridors:
            origin_id, dest_id, danger, ox, oy, dx, dy, origin_type = corridor
            
            # Determine corridor type
            corridor_data = self.db.execute_query(
                "SELECT name, corridor_type FROM corridors WHERE origin_location = %s AND destination_location = %s",
                (origin_id, dest_id), fetch='one'
            )
            if corridor_data:
                corridor_name, corridor_type = corridor_data
                if corridor_type == 'local_space' or "Approach" in corridor_name:
                    corridor_groups['approach'].append(corridor)
                elif corridor_type == 'ungated':
                    corridor_groups['ungated'].append(corridor)
                else:
                    corridor_groups['gated'].append(corridor)
            else:
                # Fallback for missing corridor data
                corridor_groups['gated'].append(corridor)
        
        # Draw corridors in order: approach -> gated -> ungated (most dangerous on top)
        for group_name, group_corridors in corridor_groups.items():
            for corridor in group_corridors:
                origin_id, dest_id, danger, ox, oy, dx, dy, origin_type = corridor
                
                # Get enhanced styling based on type and map style
                line_style = await self._get_corridor_style(
                    group_name, danger, map_style, line_width_base, alpha_base
                )
                
                # Draw main corridor line
                ax.plot([ox, dx], [oy, dy], 
                       color=line_style['color'],
                       alpha=line_style['alpha'],
                       linewidth=line_style['width'],
                       linestyle=line_style['linestyle'],
                       zorder=line_style['zorder'])
                
                # Add danger indicators for high-risk corridors
                if danger >= 4 and zoom_level == "regional":
                    await self._add_danger_indicators(ax, ox, oy, dx, dy, danger)
                
                # Add flow direction arrows for regional view
                if zoom_level == "regional" and map_style == "connections":
                    await self._add_flow_arrows(ax, ox, oy, dx, dy, line_style['color'])

    async def _get_corridor_style(self, corridor_type: str, danger: int, map_style: str, 
                                base_width: float, base_alpha: float) -> dict:
        """Get enhanced corridor styling based on type and map style"""
        
        style = {
            'width': base_width,
            'alpha': base_alpha,
            'linestyle': '-',
            'zorder': 1
        }
        
        if map_style == 'danger':
            # Danger-based coloring
            danger_colors = ['#00ff00', '#88ff00', '#ffff00', '#ff8800', '#ff0000']
            style['color'] = danger_colors[min(danger - 1, 4)]
            style['alpha'] = 0.4 + (danger * 0.1)
            style['width'] = base_width + (danger * 0.3)
            
        elif map_style == 'infrastructure':
            # Infrastructure-focused styling
            if corridor_type == 'approach':
                style['color'] = '#88ff88'  # Light green for local space
                style['alpha'] = 0.6
                style['width'] = base_width * 0.8
                style['linestyle'] = ':'
            elif corridor_type == 'gated':
                style['color'] = '#00ff88'  # Bright green for gated routes
                style['alpha'] = 0.8
                style['width'] = base_width * 1.2
            else:  # ungated
                style['color'] = '#ff6600'  # Orange for dangerous ungated
                style['alpha'] = 0.7
                style['width'] = base_width
                style['linestyle'] = '--'
                
        elif map_style == 'connections':
            # Connection flow styling
            style['color'] = '#00aaff'
            style['alpha'] = base_alpha + 0.2
            style['width'] = base_width * 1.1
            
        else:  # standard and wealth
            # Standard corridor colors
            if corridor_type == 'approach':
                style['color'] = '#666688'
            elif corridor_type == 'gated':
                style['color'] = '#4488aa'
            else:  # ungated
                style['color'] = '#aa6644'
        
        # Adjust zorder based on importance
        if corridor_type == 'ungated':
            style['zorder'] = 3  # Most dangerous on top
        elif corridor_type == 'gated':
            style['zorder'] = 2
        else:
            style['zorder'] = 1
        
        return style

    async def _add_danger_indicators(self, ax, ox: float, oy: float, dx: float, dy: float, danger: int):
        """Add visual danger indicators along high-risk corridors"""
        
        # Calculate midpoint and quarter points
        mid_x, mid_y = (ox + dx) / 2, (oy + dy) / 2
        q1_x, q1_y = (ox * 3 + dx) / 4, (oy * 3 + dy) / 4
        q3_x, q3_y = (ox + dx * 3) / 4, (oy + dy * 3) / 4
        
        danger_color = '#ff4444' if danger >= 5 else '#ff8844'
        
        # Add warning symbols using valid matplotlib markers
        warning_markers = ['^', 'v', 's']  # Triangle up, triangle down, square
        
        for i, (px, py) in enumerate([(q1_x, q1_y), (mid_x, mid_y), (q3_x, q3_y)]):
            marker = warning_markers[i % len(warning_markers)]
            ax.scatter(px, py, c=danger_color, marker=marker, s=30, alpha=0.8, zorder=4)
            
            # Add a subtle glow effect for high danger
            if danger >= 5:
                ax.scatter(px, py, c=danger_color, marker=marker, s=50, alpha=0.3, zorder=3)

    async def _add_flow_arrows(self, ax, ox: float, oy: float, dx: float, dy: float, color: str):
        """Add directional flow arrows for connection visualization"""
        
        # Calculate arrow position (1/3 along the line)
        arrow_x = ox + (dx - ox) * 0.33
        arrow_y = oy + (dy - oy) * 0.33
        
        # Calculate arrow direction
        arrow_dx = (dx - ox) * 0.1
        arrow_dy = (dy - oy) * 0.1
        
        ax.arrow(arrow_x, arrow_y, arrow_dx, arrow_dy,
                 head_width=2, head_length=2, fc=color, ec=color,
                 alpha=0.7, zorder=2)
    
    def _corridor_has_gate(self, origin_id: int, dest_id: int) -> bool:
        """Check if either endpoint of corridor is a gate"""
        gate_check = self.db.execute_query(
            '''SELECT COUNT(*) FROM locations 
               WHERE (location_id = %s OR location_id = %s) AND location_type = 'gate' ''',
            (origin_id, dest_id),
            fetch='one'
        )
        return gate_check[0] > 0
    
    async def _add_smart_labels(self, ax, locations, map_style, zoom_level, player_location=None):
        """Add smart labels with collision detection and priority-based display"""
        
        if zoom_level == "regional":
            max_labels = 15
            min_distance = 8
        else:
            max_labels = 25
            min_distance = 12
        
        # Calculate label priorities and data
        label_candidates = []
        
        for location in locations:
            loc_id, name, loc_type, x, y, wealth = location
            
            # Calculate priority
            priority = await self._calculate_label_priority(
                loc_id, loc_type, wealth, player_location, map_style
            )
            
            # Get connections for context
            connections = self.db.execute_query(
                "SELECT COUNT(*) FROM corridors WHERE origin_location = %s OR destination_location = %s",
                (loc_id, loc_id), fetch='one'
            )[0]
            
            label_candidates.append({
                'name': name,
                'x': x,
                'y': y,
                'type': loc_type,
                'wealth': wealth,
                'priority': priority,
                'connections': connections,
                'is_player': loc_id == player_location
            })
        
        # Sort by priority and apply collision detection
        label_candidates.sort(key=lambda x: x['priority'], reverse=True)
        placed_labels = []
        
        for candidate in label_candidates[:max_labels]:
            # Check for collisions with already placed labels
            collision = False
            for placed in placed_labels:
                distance = math.sqrt((candidate['x'] - placed['x'])**2 + 
                                   (candidate['y'] - placed['y'])**2)
                if distance < min_distance:
                    collision = True
                    break
            
            if not collision:
                placed_labels.append(candidate)
        
        # Draw labels with enhanced styling
        for label in placed_labels:
            await self._draw_enhanced_label(ax, label, zoom_level)

    async def _calculate_label_priority(self, loc_id: int, loc_type: str, wealth: int, 
                                      player_location: int, map_style: str) -> float:
        """Calculate label priority based on multiple factors"""
        
        priority = 0.0
        
        # Base priority by type
        type_priorities = {
            'space_station': 10.0,
            'colony': 7.0,
            'gate': 5.0,
            'outpost': 3.0
        }
        priority += type_priorities.get(loc_type, 1.0)
        
        # Wealth bonus
        priority += wealth * 0.5
        
        # Player location gets highest priority
        if loc_id == player_location:
            priority += 50.0
        
        # Connectivity bonus
        connections = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE origin_location = %s OR destination_location = %s",
            (loc_id, loc_id), fetch='one'
        )[0]
        priority += connections * 0.8
        
        # Map style specific bonuses
        if map_style == 'infrastructure' and loc_type == 'gate':
            priority += 5.0
        elif map_style == 'wealth' and wealth >= 8:
            priority += 3.0
        elif map_style == 'connections' and connections >= 4:
            priority += 4.0
        
        return priority

    async def _draw_enhanced_label(self, ax, label: dict, zoom_level: str):
        """Draw enhanced label with context-aware styling"""
        
        x, y = label['x'], label['y']
        name = label['name']
        loc_type = label['type']
        wealth = label['wealth']
        is_player = label['is_player']
        
        # Font size based on zoom and importance
        if is_player:
            fontsize = 14 if zoom_level == "regional" else 12
            weight = 'bold'
        elif loc_type == 'space_station':
            fontsize = 12 if zoom_level == "regional" else 10
            weight = 'bold'
        elif wealth >= 8:
            fontsize = 11 if zoom_level == "regional" else 9
            weight = 'bold'
        else:
            fontsize = 10 if zoom_level == "regional" else 8
            weight = 'normal'
        
        # Color coding
        label_colors = {
            'colony': '#ffaa44',
            'space_station': '#44aaff',
            'outpost': '#aaaaaa',
            'gate': '#ffff44'
        }
        
        color = label_colors.get(loc_type, 'white')
        if is_player:
            color = '#ffff00'
        
        # Enhanced name formatting
        display_name = name
        if wealth >= 9:
            display_name = f"⭐ {name}"
        elif wealth >= 8:
            display_name = f"{name} ✦"
        
        # Smart offset calculation to avoid overlapping location marker
        offset_distance = 15 if zoom_level == "regional" else 12
        offset_x = random.uniform(-offset_distance, offset_distance)
        offset_y = random.uniform(-offset_distance, offset_distance)
        
        # Ensure offset doesn't put label too close to marker
        if abs(offset_x) < 8:
            offset_x = 8 if offset_x >= 0 else -8
        if abs(offset_y) < 8:
            offset_y = 8 if offset_y >= 0 else -8
        
        # Enhanced text box
        bbox_props = dict(
            boxstyle='round,pad=0.4',
            facecolor='black',
            edgecolor=color,
            alpha=0.8,
            linewidth=1.5 if is_player else 1.0
        )
        
        ax.annotate(display_name, (x, y), 
                   xytext=(offset_x, offset_y), 
                   textcoords='offset points',
                   fontsize=fontsize,
                   color=color,
                   weight=weight,
                   ha='center', va='center',
                   bbox=bbox_props,
                   zorder=10)
    async def _style_plot_enhanced(self, ax, map_style: str, highlight_player: discord.Member, zoom_level: str):
        """Enhanced plot styling with galaxy name and current time"""
        
        # Get galaxy info and current time
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        galaxy_info = time_system.get_galaxy_info()
        galaxy_name = "Unknown Galaxy"
        current_ingame_time = None
        time_status = ""
        
        if galaxy_info:
            galaxy_name = galaxy_info[0] or "Unknown Galaxy"
            current_ingame_time = time_system.calculate_current_ingame_time()
            is_paused = galaxy_info[5] if len(galaxy_info) > 5 else False
            time_status = " (PAUSED)" if is_paused else ""
        
        # Enhanced titles with galaxy name
        titles = {
            'standard': 'Galaxy Overview',
            'infrastructure': 'Transit Infrastructure Network',
            'wealth': 'Economic Distribution Analysis',
            'connections': 'Trade Route Connectivity',
            'danger': 'Corridor Safety Assessment'
        }
        
        base_title = titles.get(map_style, 'Galaxy Map')
        
        if zoom_level == "regional":
            base_title = f"Regional View - {base_title}"
        
        if highlight_player:
            base_title += f" - {highlight_player.display_name}'s Location"
        
        # Add galaxy name to title
        full_title = f"{galaxy_name} - {base_title}"
        
        ax.set_title(full_title, color='white', fontsize=18, pad=25, weight='bold')
        
        # Enhanced axis labels
        if zoom_level == "regional":
            ax.set_xlabel('Local Coordinates (Tactical)', color='white', fontsize=12)
            ax.set_ylabel('Local Coordinates (Tactical)', color='white', fontsize=12)
        else:
            ax.set_xlabel('Galactic X Coordinate (Strategic)', color='white', fontsize=12)
            ax.set_ylabel('Galactic Y Coordinate (Strategic)', color='white', fontsize=12)
        
        # Enhanced grid
        if zoom_level == "regional":
            ax.grid(True, alpha=0.3, color='cyan', linestyle='-', linewidth=0.5)
        else:
            ax.grid(True, alpha=0.2, color='white', linestyle=':', linewidth=0.5)
        
        ax.tick_params(colors='white', labelsize=10)
        ax.set_aspect('equal', adjustable='box')
        
        # Add galaxy name and current time prominently at the top
        if current_ingame_time:
            formatted_time = time_system.format_ingame_datetime(current_ingame_time)
            # Remove the bold markdown formatting for the plot text
            clean_time = formatted_time.replace("**", "")
            galaxy_time_text = f"{galaxy_name}\nCurrent Time: {clean_time}{time_status}"
        else:
            galaxy_time_text = f"{galaxy_name}\nTime: Unknown{time_status}"
        
        # Position at top-left with background box
        ax.text(0.02, 0.98, galaxy_time_text,
               transform=ax.transAxes,
               fontsize=12, color='white',
               ha='left', va='top',
               weight='bold',
               bbox=dict(boxstyle='round,pad=0.8', facecolor='black', 
                        edgecolor='gold', alpha=0.9, linewidth=2),
               zorder=15)
        
        # Add generation timestamp and zoom indicator at bottom-right
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        info_text = f"Generated: {timestamp} | View: {zoom_level.title()}"
        if zoom_level == "regional":
            info_text += " | Scale: Tactical"
        else:
            info_text += " | Scale: Strategic"
        
        ax.text(0.99, 0.01, info_text,
               transform=ax.transAxes,
               fontsize=8, color='gray',
               ha='right', va='bottom',
               alpha=0.8)
    
    async def _add_space_decorations(self, ax):
        """Add decorative space elements"""
        
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Stars
        num_stars = 100
        star_x = np.random.uniform(xlim[0], xlim[1], num_stars)
        star_y = np.random.uniform(ylim[0], ylim[1], num_stars)
        star_sizes = np.random.uniform(0.5, 3.0, num_stars)
        
        ax.scatter(star_x, star_y, c='white', s=star_sizes, alpha=0.3, zorder=0)
        
        # Nebula patches
        for _ in range(3):
            center_x = random.uniform(xlim[0], xlim[1])
            center_y = random.uniform(ylim[0], ylim[1])
            width = random.uniform(20, 40)
            height = random.uniform(15, 30)
            
            nebula = patches.Ellipse((center_x, center_y), width, height,
                                   alpha=0.1, facecolor=random.choice(['purple', 'blue', 'green']),
                                   zorder=0)
            ax.add_patch(nebula)
    
    def _get_map_description(self, map_style: str) -> str:
        """Get thematic descriptions for each map style"""
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        galaxy_info = time_system.get_galaxy_info()
        galaxy_name = galaxy_info[0] if galaxy_info else "Unknown Galaxy"
        
        descriptions = {
            'standard': f'Navigation display for {galaxy_name} showing all registered locations and primary transit routes.',
            'infrastructure': f'Infrastructure analysis of {galaxy_name} highlighting gate networks and transit corridors.',
            'wealth': f'Economic heat map of {galaxy_name} displaying wealth distribution across settlements.',
            'connections': f'Trade network visualization for {galaxy_name} showing route connectivity and traffic density.',
            'danger': f'Hazard assessment map for {galaxy_name} indicating corridor radiation levels and structural integrity.'
        }
        return descriptions.get(map_style, f'Tactical display of {galaxy_name}.')
    
    def _get_legend_text(self, map_style: str, show_routes: bool = True) -> str:
        """Updated legends with route visibility and clearer type descriptions"""
        
        # Base location markers (always shown)
        location_text = '● Colonies\n▲ Space Stations\n■ Outposts\n◆ Transit Gates'
        
        # Route descriptions (only if routes are shown)
        route_text = ""
        if show_routes:
            if map_style == 'standard':
                route_text = '\n\nROUTE TYPES:\n━━ Gated Corridors (Safe, Fast)\n┅┅ Ungated Routes (Dangerous)\n⋯⋯ Local Space (Short Hops)'
            elif map_style == 'infrastructure':
                route_text = '\n\nCORRIDOR NETWORK:\n━━ Inter-System (Gated)\n┅┅ Direct Routes (Ungated)\n⋯⋯ Station Access (Local)'
            elif map_style == 'danger':
                route_text = '\n\nDANGER LEVELS:\nGreen: Safe (1-2)\nYellow: Moderate (3)\nOrange: Dangerous (4)\nRed: Extreme (5)'
        
        # Combine based on map style
        if map_style == 'wealth':
            return 'ECONOMIC STATUS:\nGreen: Wealthy (8-10)\nYellow: Moderate (5-7)\nRed: Poor (1-4)\nSize = Economic Power'
        elif map_style == 'connections':
            base = 'CONNECTIVITY:\nBrighter/Larger = More Connected'
            if show_routes:
                base += '\nBlue lines = Active Routes'
            return base
        else:
            return location_text + route_text
            
    async def _add_enhanced_legend(self, ax, map_style: str, zoom_level: str, 
                                 locations: list, corridors: list):
        """Add enhanced legend with matplotlib-compatible symbols"""
        
        # Position legend based on zoom level
        if zoom_level == "regional":
            legend_x = 0.02
            legend_y = 0.85  # Moved up slightly to avoid galaxy info box
            font_size = 10
        else:
            legend_x = 0.02
            legend_y = 0.82  # Moved up slightly to avoid galaxy info box
            font_size = 9
        
        legend_items = []
        
        # Map style specific legends with matplotlib-compatible symbols
        if map_style == 'infrastructure':
            legend_items = [
                "LOCATION TYPES:",
                "■  Space Stations", 
                "●  Colonies", 
                "▲  Outposts", 
                "◆  Transit Gates",
                "",
                "CORRIDOR TYPES:",
                "──  Gated Corridors (Safe)", 
                "┈┈  Local Space", 
                "╌╌  Ungated (Dangerous)"
            ]
        elif map_style == 'wealth':
            legend_items = [
                "ECONOMIC INDICATORS:",
                "Green   Wealthy (8-10)", 
                "Yellow  Moderate (5-7)", 
                "Red     Poor (1-4)", 
                "* Gold  Premium (9+)", 
                "",
                "Size = Economic Power"
            ]
        elif map_style == 'connections':
            legend_items = [
                "CONNECTIVITY ANALYSIS:",
                "Bright/Large = Well Connected",
                "→  Traffic Flow Direction", 
                "Blue Lines = Active Routes",
                "",
                "Size = Connection Count"
            ]
        elif map_style == 'danger':
            legend_items = [
                "CORRIDOR DANGER LEVELS:",
                "Green   Safe (1-2)", 
                "Yellow  Moderate (3)",
                "Orange  Dangerous (4)", 
                "Red     Extreme (5)", 
                "",
                "!  Hazard Warnings"
            ]
        else:  # standard
            legend_items = [
                "LOCATION TYPES:",
                "■  Space Stations", 
                "●  Colonies", 
                "▲  Outposts", 
                "◆  Gates",
                "",
                "OTHER:",
                "──  Corridor Routes", 
                "★  You Are Here", 
                "*  High Value Location"
            ]
        
        # Add statistical information for regional view
        if zoom_level == "regional":
            stats = await self._get_regional_stats(locations, corridors)
            legend_items.extend(["", "REGIONAL STATISTICS:"] + stats)
        
        # Add time scale information
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        galaxy_info = time_system.get_galaxy_info()
        
        if galaxy_info:
            time_scale = galaxy_info[2] if len(galaxy_info) > 2 else 4.0
            is_paused = galaxy_info[5] if len(galaxy_info) > 5 else False
            
            legend_items.extend([
                "",
                "TIME SYSTEM:",
                f"Scale: {time_scale}x speed",
                f"Status: {'PAUSED' if is_paused else 'RUNNING'}"
            ])
        
        # Draw legend box
        legend_text = "\n".join(legend_items)
        
        ax.text(legend_x, legend_y, legend_text,
               transform=ax.transAxes,
               fontsize=font_size,
               verticalalignment='top',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='black', 
                        edgecolor='white', alpha=0.9),
               color='white',
               family='monospace')    
    async def _add_player_context(self, ax, locations: list, player_location: int, focus_center: tuple):
        """Add contextual information around player location"""
        
        if not focus_center:
            return
        
        fx, fy = focus_center
        
        # Find player's location details
        player_loc_info = None
        for loc in locations:
            if loc[0] == player_location:
                player_loc_info = loc
                break
        
        if not player_loc_info:
            return
        
        loc_id, name, loc_type, x, y, wealth = player_loc_info
        
        # Add proximity rings around player
        proximity_rings = [
            {'radius': 10, 'color': 'yellow', 'alpha': 0.2, 'label': 'Local'},
            {'radius': 20, 'color': 'orange', 'alpha': 0.15, 'label': 'Regional'},
            {'radius': 35, 'color': 'red', 'alpha': 0.1, 'label': 'Extended'}
        ]
        
        for ring in proximity_rings:
            circle = plt.Circle((fx, fy), ring['radius'], fill=False,
                              color=ring['color'], alpha=ring['alpha'],
                              linewidth=1, linestyle='--', zorder=1)
            ax.add_patch(circle)
        
        # Add nearby location highlights
        nearby_locations = []
        for loc in locations:
            if loc[0] != player_location:
                loc_x, loc_y = loc[3], loc[4]
                distance = math.sqrt((loc_x - fx)**2 + (loc_y - fy)**2)
                if distance <= 15:  # Close proximity
                    nearby_locations.append((loc, distance))
        
        # Highlight closest 3 locations
        nearby_locations.sort(key=lambda x: x[1])
        for i, (loc, distance) in enumerate(nearby_locations[:3]):
            loc_x, loc_y = loc[3], loc[4]
            color_intensity = 1.0 - (i * 0.3)  # Fade for further locations
            
            # Draw connection line
            ax.plot([fx, loc_x], [fy, loc_y], 
                   color='cyan', alpha=color_intensity * 0.5, 
                   linewidth=1, linestyle=':', zorder=1)
            
            # Distance label
            ax.text((fx + loc_x) / 2, (fy + loc_y) / 2, f"{distance:.1f}",
                   fontsize=8, color='cyan', alpha=color_intensity,
                   ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.7))
    async def _get_regional_stats(self, locations: list, corridors: list) -> list:
        """Get statistical information for regional view"""
        
        stats = []
        
        # Location counts
        type_counts = {}
        total_wealth = 0
        
        for loc in locations:
            loc_type = loc[2]
            wealth = loc[5]
            type_counts[loc_type] = type_counts.get(loc_type, 0) + 1
            total_wealth += wealth
        
        # Format type counts
        for loc_type, count in type_counts.items():
            type_name = loc_type.replace('_', ' ').title()
            stats.append(f"{type_name}s: {count}")
        
        # Average wealth
        if locations:
            avg_wealth = total_wealth / len(locations)
            stats.append(f"Avg Wealth: {avg_wealth:.1f}")
        
        # Corridor information
        if corridors:
            stats.append(f"Routes: {len(corridors)}")
            
            # Danger analysis
            dangers = [c[2] for c in corridors]
            avg_danger = sum(dangers) / len(dangers)
            max_danger = max(dangers)
            stats.append(f"Avg Danger: {avg_danger:.1f}")
            stats.append(f"Max Danger: {max_danger}")
        
        return stats
    async def _get_galaxy_stats(self) -> str:
        """Get galaxy statistics"""
        total_locations = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
        total_corridors = self.db.execute_query("SELECT COUNT(DISTINCT name) FROM corridors", fetch='one')[0]
        gates = self.db.execute_query("SELECT COUNT(*) FROM locations WHERE location_type = 'gate'", fetch='one')[0]
        
        return f"Locations: {total_locations}\nTransit Gates: {gates}\nCorridors: {total_corridors}"
    
    # ... (keep existing map and info commands)
    async def _generate_built_in_repeaters(self, conn, all_locations: List[Dict]) -> int:
        """Generates built-in radio repeaters at major locations using batch processing."""
        repeaters_to_insert = []
        total_created = 0
        batch_size = 100  # Process locations in batches to avoid hanging
        
        print(f"📡 Processing {len(all_locations)} locations for repeater installation...")
        
        for i, location in enumerate(all_locations):
            repeater_chance = 0.0
            loc_type = location['type']
            wealth = location['wealth_level']

            if loc_type == 'space_station': repeater_chance = 0.4 if wealth >= 8 else 0.2
            elif loc_type == 'colony': repeater_chance = 0.15 if wealth >= 9 else 0.05
            elif loc_type == 'gate': repeater_chance = 0.3
            
            if random.random() < repeater_chance:
                if loc_type == 'space_station':
                    rec_range, trans_range = 12, 8
                elif loc_type == 'gate':
                    rec_range, trans_range = 10, 6
                else: # colony
                    rec_range, trans_range = 8, 5
                
                repeaters_to_insert.append((location['id'], rec_range, trans_range))
            
            # Process in batches to avoid hanging and provide progress updates
            if len(repeaters_to_insert) >= batch_size or i == len(all_locations) - 1:
                if repeaters_to_insert:
                    query = '''INSERT INTO repeaters 
                               (location_id, repeater_type, receive_range, transmit_range, is_active)
                               VALUES (%s, 'built_in', %s, %s, true)'''
                    self.db.executemany_in_transaction(conn, query, repeaters_to_insert)
                    total_created += len(repeaters_to_insert)
                    print(f"📡 Installed {len(repeaters_to_insert)} repeaters (batch {i//batch_size + 1}), total: {total_created}")
                    repeaters_to_insert = []
                
                # Yield control back to the event loop
                await asyncio.sleep(0)
        
        print(f"📡 Created {total_created} built-in repeaters total.")
        return total_created
    async def _ensure_galactic_news_setup(self, guild: discord.Guild, galaxy_name: str):
        """Ensure galactic news channel is configured and send connection announcement"""
        
        # Check if galactic updates channel is already configured
        updates_channel_id = self.db.execute_query(
            "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = %s",
            (guild.id,),
            fetch='one'
        )
        
        news_channel = None
        if updates_channel_id and updates_channel_id[0]:
            news_channel = guild.get_channel(updates_channel_id[0])
        
        # If no configured channel, try to find the galactic news channel
        if not news_channel:
            news_channel_name = "📡-galactic-news"
            for channel in guild.text_channels:
                if channel.name == news_channel_name:
                    news_channel = channel
                    # Update database configuration
                    existing_config = self.db.execute_query(
                        "SELECT guild_id FROM server_config WHERE guild_id = %s",
                        (guild.id,),
                        fetch='one'
                    )
                    
                    if existing_config:
                        self.db.execute_query(
                            "UPDATE server_config SET galactic_updates_channel_id = %s WHERE guild_id = %s",
                            (news_channel.id, guild.id)
                        )
                    else:
                        self.db.execute_query(
                            "INSERT INTO server_config (guild_id, galactic_updates_channel_id) VALUES (%s, %s)",
                            (guild.id, news_channel.id)
                        )
                    
                    print(f"📰 Configured existing galactic news channel: {news_channel.id}")
                    break
        
        # Send connection announcement if we have a news channel
        if news_channel:
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                await news_cog.queue_news(
                    guild.id,
                    'admin_announcement',
                    'Galactic News Network Relay Established',
                    f'The Galactic News Network has successfully established a communication relay with {galaxy_name}. All major galactic events, infrastructure changes, and emergency broadcasts will now be transmitted to this sector with appropriate delays based on interstellar communication protocols. Welcome to the connected galaxy.',
                    None  # No specific location for this administrative message
                )
                print(f"📰 Queued galactic news connection announcement for {galaxy_name}")    
    async def _clear_existing_galaxy_data(self, conn):
        """Clear existing galaxy data in proper order to avoid foreign key constraints"""
        # Clear in reverse dependency order to avoid foreign key issues
        print("🔧 DEBUG: Starting galaxy data clearing process...")
        
        # First, clear tables that depend on locations
        print("🔧 DEBUG: Clearing home-related tables...")
        self.db.execute_in_transaction(conn, "DELETE FROM home_activities")
        self.db.execute_in_transaction(conn, "DELETE FROM home_interiors")
        self.db.execute_in_transaction(conn, "DELETE FROM home_market_listings")
        self.db.execute_in_transaction(conn, "DELETE FROM home_invitations")
        self.db.execute_in_transaction(conn, "DELETE FROM location_homes")
        print("🔧 DEBUG: Home tables cleared")
        
        print("🔧 DEBUG: Clearing location-dependent tables...")
        self.db.execute_in_transaction(conn, "DELETE FROM character_reputation")
        self.db.execute_in_transaction(conn, "DELETE FROM location_items")
        self.db.execute_in_transaction(conn, "DELETE FROM location_logs")
        self.db.execute_in_transaction(conn, "DELETE FROM shop_items")
        self.db.execute_in_transaction(conn, "DELETE FROM jobs")
        self.db.execute_in_transaction(conn, "DELETE FROM job_tracking")
        self.db.execute_in_transaction(conn, "DELETE FROM location_storage")
        self.db.execute_in_transaction(conn, "DELETE FROM location_income_log")
        self.db.execute_in_transaction(conn, "DELETE FROM location_access_control")
        self.db.execute_in_transaction(conn, "DELETE FROM location_upgrades")
        self.db.execute_in_transaction(conn, "DELETE FROM location_ownership")
        self.db.execute_in_transaction(conn, "DELETE FROM location_economy")
        self.db.execute_in_transaction(conn, "DELETE FROM economic_events")
        print("🔧 DEBUG: Location-dependent tables cleared")
        
        # Clear NPC related tables
        print("🔧 DEBUG: Clearing NPC tables...")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_respawn_queue")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_inventory")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_trade_inventory")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_jobs")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_job_completions")
        self.db.execute_in_transaction(conn, "DELETE FROM static_npcs")
        self.db.execute_in_transaction(conn, "DELETE FROM dynamic_npcs")
        print("🔧 DEBUG: NPC tables cleared")
        
        # Clear black market tables
        print("🔧 DEBUG: Clearing black market tables...")
        self.db.execute_in_transaction(conn, "DELETE FROM black_market_items")
        self.db.execute_in_transaction(conn, "DELETE FROM black_markets")
        print("🔧 DEBUG: Black market tables cleared")
        
        # Clear sub-locations and repeaters
        print("🔧 DEBUG: Clearing sub-locations and repeaters...")
        self.db.execute_in_transaction(conn, "DELETE FROM sub_locations")
        self.db.execute_in_transaction(conn, "DELETE FROM repeaters")
        print("🔧 DEBUG: Sub-locations and repeaters cleared")
        
        # Clear travel sessions that reference corridors/locations
        print("🔧 DEBUG: Clearing travel and corridor data...")
        self.db.execute_in_transaction(conn, "DELETE FROM travel_sessions")
        self.db.execute_in_transaction(conn, "DELETE FROM corridor_events")
        print("🔧 DEBUG: Travel and corridor events cleared")
        
        # Finally clear corridors and locations
        print("🔧 DEBUG: Clearing main corridors and locations...")
        self.db.execute_in_transaction(conn, "DELETE FROM corridors")
        self.db.execute_in_transaction(conn, "DELETE FROM locations")
        print("🔧 DEBUG: Main corridors and locations cleared")
        
        # Clear history and news
        print("🔧 DEBUG: Clearing history and news...")
        self.db.execute_in_transaction(conn, "DELETE FROM galactic_history")
        self.db.execute_in_transaction(conn, "DELETE FROM news_queue")
        print("🔧 DEBUG: History and news cleared")
        
        # Clear endgame config if exists
        print("🔧 DEBUG: Clearing endgame config...")
        self.db.execute_in_transaction(conn, "DELETE FROM endgame_config")
        self.db.execute_in_transaction(conn, "DELETE FROM endgame_evacuations")
        print("🔧 DEBUG: Endgame config cleared")
        
        print("🗑️ Cleared existing galaxy data in proper order")
        
    async def _generate_initial_location_logs(self, conn, all_locations: List[Dict], start_date_obj) -> int:
        """Generate initial log books for locations with ultra-aggressive optimization for large galaxies"""
        from utils.npc_data import generate_npc_name, get_occupation
        
        # Commit the current transaction immediately to avoid long locks
        if conn:
            self.db.commit_transaction(conn)
            conn = None
        
        print(f"📜 Generating log books for {len(all_locations)} locations...")
        
        locations_with_logs = 0
        total_entries_created = 0
        
        # Ultra-small batch sizes for massive galaxies
        location_chunk_size = 3  # Process only 3 locations at a time
        batch_size = 15  # Very small batches for database inserts
        current_batch = []
        
        # Pre-filter locations to avoid processing derelicts
        valid_locations = [loc for loc in all_locations if not loc.get('is_derelict', False)]
        print(f"📜 Processing {len(valid_locations)} non-derelict locations for log books...")
        
        # Process locations in tiny chunks with frequent yielding
        for chunk_start in range(0, len(valid_locations), location_chunk_size):
            chunk_end = min(chunk_start + location_chunk_size, len(valid_locations))
            location_chunk = valid_locations[chunk_start:chunk_end]
            
            # Pre-generate all log data for this chunk without database calls
            chunk_log_entries = []
            
            for location in location_chunk:
                # 25% chance for each location to have a log book (same as original)
                if random.random() < 0.25:
                    locations_with_logs += 1
                    num_entries = random.randint(3, 5)  # Same range as original
                    
                    # Pre-generate all entries for this location
                    for _ in range(num_entries):
                        # Generate NPC author efficiently
                        first_name, last_name = generate_npc_name()
                        wealth_level = location.get('wealth_level', 5)
                        occupation = get_occupation(location['type'], wealth_level)
                        name_format = f"{first_name} {last_name}, {occupation}"
                        
                        # Get message using optimized selection
                        message = self._get_optimized_log_message(location['type'])
                        
                        # Generate historical date
                        days_ago = random.randint(1, 365)
                        hours_ago = random.randint(0, 23)
                        entry_time = start_date_obj - timedelta(days=days_ago, hours=hours_ago)
                        
                        # Add to chunk entries
                        chunk_log_entries.append(
                            (location['id'], 0, name_format, message, entry_time.isoformat(), True)
                        )
            
            # Add chunk entries to current batch
            current_batch.extend(chunk_log_entries)
            total_entries_created += len(chunk_log_entries)
            
            # Insert when batch is ready, using micro-transactions
            if len(current_batch) >= batch_size:
                await self._insert_log_batch_micro_transaction(current_batch[:batch_size])
                current_batch = current_batch[batch_size:]
                
                # Aggressive yielding after each micro-transaction
                await asyncio.sleep(0.1)
            
            # Yield control after each chunk
            await asyncio.sleep(0.05)
            
            # Progress reporting every 25 locations
            if chunk_start % 25 == 0 and chunk_start > 0:
                progress = (chunk_start / len(valid_locations)) * 100
                print(f"    📜 Log generation progress: {progress:.0f}% ({chunk_start}/{len(valid_locations)}) - {total_entries_created} entries created")
                
                # Extra yield for progress reporting
                await asyncio.sleep(0.1)
        
        # Insert any remaining entries
        while current_batch:
            batch_to_insert = current_batch[:batch_size]
            current_batch = current_batch[batch_size:]
            await self._insert_log_batch_micro_transaction(batch_to_insert)
            await asyncio.sleep(0.05)
        
        print(f"📜 Generated log books for {locations_with_logs} locations with {total_entries_created} total entries")
        return locations_with_logs

    async def _insert_log_batch_micro_transaction(self, batch_data: List[tuple]):
        """Insert log entries in completely independent micro-transaction with retry logic"""
        if not batch_data:
            return
        
        # Retry logic for database lock issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait a bit if this is a retry
                if attempt > 0:
                    await asyncio.sleep(0.2 * attempt)
                
                # Use completely independent micro-transaction
                micro_conn = self.db.begin_transaction()
                
                query = '''INSERT INTO location_logs 
                           (location_id, author_id, author_name, message, posted_at, is_generated)
                           VALUES (%s, %s, %s, %s, %s, %s)'''
                self.db.executemany_in_transaction(micro_conn, query, batch_data)
                self.db.commit_transaction(micro_conn)
                
                # Success - break out of retry loop
                break
                
            except Exception as e:
                if micro_conn:
                    try:
                        self.db.rollback_transaction(micro_conn)
                    except:
                        pass
                
                if "database lock" in str(e).lower() and attempt < max_retries - 1:
                    print(f"⚠️ Database lock in log generation, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    print(f"❌ Error inserting log batch: {e}")
                    if attempt == max_retries - 1:
                        print("⚠️ Skipping this log batch to continue generation")
                    break
            finally:
                micro_conn = None

    def _get_optimized_log_message(self, location_type: str) -> str:
        """Get a random log message using optimized selection without loading large arrays"""
        
        # Use smaller, focused message pools with weighted selection
        # 40% chance for location-specific, 60% for generic (same as original)
        if random.random() < 0.4:
            return self._get_location_specific_message(location_type)
        else:
            return self._get_generic_log_message()

    def _get_location_specific_message(self, location_type: str) -> str:
        """Get location-specific message using efficient selection"""
        
        # Smaller, curated pools for each type (maintaining variety but reducing memory)
        type_message_pools = {
            'colony': [
                "Agricultural output exceeding projections this quarter.",
                "Population growth steady. Housing expansion approved.", 
                "Mining operations proceeding on schedule.",
                "Trade relations with neighboring systems improving.",
                "Colonial infrastructure upgrade project initiated.",
                "Atmospheric processors maintaining optimal conditions.",
                "New settlers orientation program completed successfully.",
                "Terraforming efforts progressing as planned.",
                "Water recycling efficiency at 98%.",
                "Biodome experiencing minor issues, contained.",
                "Educational programs seeing increased enrollment.",
                "Defensive perimeter generators at full power.",
                "Medical facilities reporting low disease incidence.",
                "Energy grid experiencing peak demand fluctuations.",
                "Geological survey discovered new resources.",
                "Long-range probe returned with stellar data.",
                "Cultural exchange program approved.",
                "Resource extraction quotas met ahead of deadline.",
                "How much further to Earth%s",
                "Another quiet day. Good for catching up on paperwork."
            ],
            'space_station': [
                "Docking bay efficiency improved with new protocols.",
                "Station rotation mechanics functioning normally.",
                "Merchant traffic up 15% compared to last cycle.",
                "Artificial gravity generators running smoothly.",
                "Recycling systems processing at maximum efficiency.",
                "Tourist accommodations at capacity.",
                "Station-wide maintenance inspection scheduled.",
                "Emergency response drill conducted successfully.",
                "Life support scrubbers cleaned and calibrated.",
                "Exterior hull integrity check passed.",
                "Research lab reporting deep space anomalies.",
                "Crew rotation completed without incident.",
                "Zero-G training for new recruits underway.",
                "Communications array received distress signal.",
                "Internal security patrol routes optimized.",
                "Cafeteria menu updated with hydroponic produce.",
                "Observatory windows cleaned, visibility excellent.",
                "Module atmospheric pressure stable.",
                "Power conduits showing minor thermal variations.",
                "How much further to Earth%s"
            ],
            'outpost': [
                "Long-range communications restored after failure.",
                "Supply cache inventory updated and secured.",
                "Mineral survey detected promising ores.",
                "Perimeter sensors showing normal activity.",
                "Generator fuel reserves adequate for six months.",
                "Weather monitoring equipment calibrated.",
                "Emergency beacon tested and operational.",
                "Staff rotation schedule updated.",
                "Isolation protocols reviewed and updated.",
                "Automated drills reached target depth.",
                "Seismic activity within expected parameters.",
                "Wildlife deterrent system activated.",
                "Excavation team unearthed ancient artifacts.",
                "Solar array alignment optimized.",
                "Dust storm reduced visibility to zero.",
                "Water purification at peak capacity.",
                "Relay station signal strength improved.",
                "Drone reconnaissance returned with mapping data.",
                "Geothermal conduit sealed for repair.",
                "Another quiet shift on the frontier."
            ],
            'gate': [
                "Corridor stability within acceptable variance.",
                "Transit queue processing efficiently.",
                "Gate energy consumption optimized.",
                "Safety protocols updated per incidents.",
                "Decontamination procedures enhanced.",
                "Navigation beacon alignment verified.",
                "Traffic control systems upgraded.",
                "Emergency transit procedures drilled.",
                "Inter-system data packets flowing normally.",
                "Security checkpoint contraband seizure.",
                "Corridor stabilizer operating normally.",
                "Anomaly detection on standby.",
                "Personnel transit logs audited.",
                "Customs forms updated with new tariffs.",
                "Scheduled shutdown for power coupling replacement.",
                "Transit gate maintenance completed.",
                "Energy field fluctuations minimal.",
                "Gate synchronization nominal.",
                "Passenger manifest verification complete.",
                "How much further to Earth%s"
            ]
        }
        
        pool = type_message_pools.get(location_type, type_message_pools['colony'])
        return random.choice(pool)

    def _get_generic_log_message(self) -> str:
        """Get generic message using efficient random selection"""
        
        # Create message categories for variety without huge arrays
        categories = [
            # System status messages
            [
                "All systems nominal. No incidents to report.",
                "Routine maintenance completed successfully.",
                "Equipment calibration finished, ready for operation.",
                "Environmental conditions stable.",
                "Security sweep complete. All clear.",
                "Communications array functioning normally.",
                "Power grid operating at optimal efficiency.",
                "Navigation systems updated and verified.",
                "Emergency systems tested and operational.",
                "Structural integrity checks passed."
            ],
            # Personal/crew messages  
            [
                "Another quiet day. Good for paperwork.",
                "Coffee supply running low again.",
                "Met interesting travelers today.",
                "Long shift, but someone has to keep things running.", 
                "Received message from family. Always nice.",
                "New arrival seemed nervous. First timer probably.",
                "Reminder to check backup generators tomorrow.",
                "Quiet night shift. Perfect for reading.",
                "Looking forward to next leave.",
                "The stars really make you feel small."
            ],
            # Technical/operational messages
            [
                "Diagnostic complete. Minor adjustments made.",
                "Software update installed successfully.",
                "Preventive maintenance on critical systems.",
                "Backup systems tested and functional.",
                "Network connectivity stable.",
                "Sensor array recalibrated.",
                "Performance metrics within parameters.",
                "System logs reviewed. No errors found.",
                "Component replacement scheduled.",
                "Energy consumption holding steady."
            ],
            # Trade/economic messages
            [
                "Cargo manifests reviewed and approved.",
                "Price negotiations concluded fairly.",
                "Supply shipment arrived on schedule.",
                "Market analysis complete. Prices steady.",
                "Trade agreement signed successfully.",
                "Customs inspection finished.",
                "Freight scheduling optimized.",
                "Quality assessment completed.",
                "Export permits processed.",
                "Trade route security briefing attended."
            ]
        ]
        
        # Select random category, then random message from that category
        category = random.choice(categories)
        return random.choice(category)

    async def _ensure_database_ready_for_history(self):
        """Ensure database is ready for history generation after potential resets"""
        try:
            # Brief pause before history generation
            await asyncio.sleep(1.0)
            
            # Test database connectivity with a simple query
            self.db.execute_query("SELECT COUNT(*) FROM locations WHERE is_generated = true", fetch='one')
            print("✅ Database connectivity verified for history generation")
            
        except Exception as e:
            print(f"⚠️ Database readiness check failed: {e}")
            # Don't raise - let history generation attempt to proceed
            # The history generator has its own error handling

async def setup(bot):
    await bot.add_cog(GalaxyGeneratorCog(bot))