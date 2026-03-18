"""
Front Office - Player Comparisons Database
Comprehensive MLB comp database using 1985-2020 era players.
Organized by archetype with tool profiles and career details.
Phase 2 expansion: 150+ players across 25+ archetypes.
"""
import random
from typing import Optional


# Position player archetypes (1985-2020 era)
POSITION_COMPS = {
    # Power-first corner bats
    "power_corner": [
        {
            "name": "Mark McGwire",
            "position": "1B/DH",
            "years": "1986-2001",
            "peak_stats": "70 HR, 147 RBI (1998)",
            "contact": 40, "power": 80, "run": 30, "field": 40, "arm": 35,
            "description": "Pure power stroke with limited OBP. Low BA, high HR rate, machete swinger.",
            "career_summary": "Hit 583 HRs in 16 seasons. Dominant power but poor speed and defense."
        },
        {
            "name": "Jim Thome",
            "position": "1B/DH",
            "years": "1991-2012",
            "peak_stats": "52 HR, 131 RBI (2002)",
            "contact": 50, "power": 80, "run": 25, "field": 35, "arm": 40,
            "description": "Plus power with respectable contact rates. Patient approach, above-average strikeout rate.",
            "career_summary": "600+ HR hitter with excellent BB rate. Steady power over 22 seasons."
        },
        {
            "name": "Albert Belle",
            "position": "LF",
            "years": "1989-2000",
            "peak_stats": "50 HR, 148 RBI (1995)",
            "contact": 55, "power": 75, "run": 40, "field": 45, "arm": 60,
            "description": "Aggressive gap hitter with power to all fields. Below-average speed but solid arm.",
            "career_summary": "Hit .290 with 381 HRs. Consistent RBI producer."
        },
        {
            "name": "Mo Vaughn",
            "position": "1B/DH",
            "years": "1991-2003",
            "peak_stats": "40 HR, 126 RBI (1996)",
            "contact": 50, "power": 75, "run": 35, "field": 35, "arm": 40,
            "description": "Powerful lefty hitter with good batting average. Limited speed and defense.",
            "career_summary": "MVP-caliber player at peak. 355 career HRs with 1,064 RBIs."
        },
        {
            "name": "Carlos Delgado",
            "position": "1B/DH",
            "years": "1991-2009",
            "peak_stats": "42 HR, 145 RBI (1999)",
            "contact": 55, "power": 75, "run": 30, "field": 40, "arm": 40,
            "description": "Left-handed power hitter with excellent walk rate. Career power accumulator.",
            "career_summary": "Hit 473 HRs in 19 seasons with excellent plate discipline."
        },
        {
            "name": "Frank Thomas",
            "position": "DH/1B",
            "years": "1990-2008",
            "peak_stats": "42 HR, 128 RBI (2000)",
            "contact": 60, "power": 80, "run": 30, "field": 35, "arm": 40,
            "description": "Two-time MVP with combination of power and contact. Excellent plate discipline.",
            "career_summary": "521 HRs with elite BB rate. One of DH era's greatest players."
        },
        {
            "name": "Jeff Bagwell",
            "position": "1B",
            "years": "1991-2005",
            "peak_stats": "39 HR, 128 RBI (1994)",
            "contact": 60, "power": 75, "run": 50, "field": 60, "arm": 45,
            "description": "All-around first baseman. Good speed and defense for position. Excellent hitter.",
            "career_summary": "449 HRs with solid defense. Good speed, excellent OPS."
        },
    ],

    # Contact-first speedsters
    "contact_speedster": [
        {
            "name": "Kenny Lofton",
            "position": "CF",
            "years": "1991-2007",
            "peak_stats": "5 HR, 66 RBI (1992)",
            "contact": 75, "power": 30, "run": 80, "field": 70, "arm": 55,
            "description": "Table-setter supreme. Elite speed and center field defense. Low power but leadoff-caliber bat.",
            "career_summary": "474 SB in 17 seasons. Career .299 hitter with minimal power."
        },
        {
            "name": "Johnny Damon",
            "position": "LF/CF",
            "years": "1995-2012",
            "peak_stats": "16 HR, 93 RBI (2006)",
            "contact": 70, "power": 45, "run": 70, "field": 60, "arm": 50,
            "description": "Versatile outfielder with high average and good speed. Steady defender.",
            "career_summary": "Hit .295 with 235 HRs over 18 seasons. 2,769 hits and smart baserunner."
        },
        {
            "name": "Ichiro Suzuki",
            "position": "RF/CF",
            "years": "2001-2012 (MLB)",
            "peak_stats": "15 HR, 69 RBI (2004)",
            "contact": 80, "power": 50, "run": 75, "field": 70, "arm": 70,
            "description": "Unique elite contact hitter from Japan. Singles and speed, improved power later.",
            "career_summary": "Hit .330 with 3,089 hits in MLB. Exceptional hand-eye coordination."
        },
        {
            "name": "Juan Pierre",
            "position": "LF/CF",
            "years": "2000-2011",
            "peak_stats": "3 HR, 36 RBI (2003)",
            "contact": 75, "power": 25, "run": 80, "field": 70, "arm": 50,
            "description": "Pure speed and contact player. Minimal power, excellent average. Gap hitter.",
            "career_summary": "Career .295 hitter with 614 SB. Reliable defensive outfielder."
        },
        {
            "name": "Willy Taveras",
            "position": "CF",
            "years": "2004-2010",
            "peak_stats": "1 HR, 29 RBI (2005)",
            "contact": 65, "power": 20, "run": 80, "field": 65, "arm": 45,
            "description": "Blazing speed with minimal offensive impact. Slap hitter with limited patience.",
            "career_summary": "Career .271 hitter with 154 SB. Speed-only profile."
        },
        {
            "name": "Luis Castillo",
            "position": "2B",
            "years": "1996-2010",
            "peak_stats": "3 HR, 49 RBI (2000)",
            "contact": 75, "power": 20, "run": 75, "field": 70, "arm": 55,
            "description": "Contact-oriented second baseman with plus speed. High average, no power.",
            "career_summary": "Career .290 hitter with 370 SB. Three-time All-Star."
        },
    ],

    # Five-tool center fielders
    "five_tool_cf": [
        {
            "name": "Ken Griffey Jr.",
            "position": "CF",
            "years": "1989-2010",
            "peak_stats": "56 HR, 147 RBI (1997)",
            "contact": 70, "power": 80, "run": 70, "field": 75, "arm": 70,
            "description": "Defining five-tool player. Plus skills in all areas. Beautiful swing.",
            "career_summary": "630 HRs, great defense and speed. Preeminent player of the 1990s."
        },
        {
            "name": "Andruw Jones",
            "position": "CF",
            "years": "1996-2012",
            "peak_stats": "51 HR, 128 RBI (2006)",
            "contact": 60, "power": 75, "run": 65, "field": 80, "arm": 75,
            "description": "Exceptional center fielder with plus defense and arm. Power-speed combo.",
            "career_summary": "434 HRs with elite outfield defense (10 Gold Gloves)."
        },
        {
            "name": "Jim Edmonds",
            "position": "CF",
            "years": "1993-2010",
            "peak_stats": "42 HR, 111 RBI (2004)",
            "contact": 65, "power": 75, "run": 65, "field": 80, "arm": 70,
            "description": "Superb defensive center fielder with power. Athletic, excellent jumps.",
            "career_summary": "393 HRs with 8 Gold Gloves. Elite defensive skills."
        },
        {
            "name": "Torii Hunter",
            "position": "CF/RF",
            "years": "1997-2015",
            "peak_stats": "28 HR, 102 RBI (2002)",
            "contact": 65, "power": 70, "run": 70, "field": 80, "arm": 80,
            "description": "Versatile outfielder with plus defense and arm. Good speed and gap power.",
            "career_summary": "353 HRs with elite defense. Consistent 25-HR threat with GG awards."
        },
        {
            "name": "Mike Cameron",
            "position": "CF",
            "years": "1995-2011",
            "peak_stats": "25 HR, 110 RBI (2001)",
            "contact": 55, "power": 65, "run": 70, "field": 80, "arm": 65,
            "description": "Outstanding defensive center fielder with power-speed combo. Strikeout-prone but athletic.",
            "career_summary": "278 HRs with elite defense. Four-HR game in 2002."
        },
        {
            "name": "Andrew Jones (peak)",
            "position": "CF",
            "years": "1996-2012",
            "peak_stats": "36 HR, 104 RBI (2000)",
            "contact": 55, "power": 70, "run": 65, "field": 80, "arm": 75,
            "description": "Elite glove in center with above-average power. Aggressive hitter with swing-and-miss.",
            "career_summary": "See Andruw Jones entry. Peak years featured elite defense plus 30+ HR power."
        },
    ],

    # Slick-fielding shortstops
    "slick_ss": [
        {
            "name": "Omar Vizquel",
            "position": "SS",
            "years": "1989-2011",
            "peak_stats": "5 HR, 51 RBI (1994)",
            "contact": 70, "power": 25, "run": 50, "field": 80, "arm": 75,
            "description": "Master shortstop with elite defense. Outstanding glove, weak bat.",
            "career_summary": "11-time Gold Glove winner. Hit .272 with minimal power but excellent defense."
        },
        {
            "name": "Rey Ordonez",
            "position": "SS",
            "years": "1996-2008",
            "peak_stats": "6 HR, 44 RBI (2000)",
            "contact": 65, "power": 20, "run": 45, "field": 85, "arm": 80,
            "description": "Defensive genius with fantastic glove work. Poor bat control and limited power.",
            "career_summary": "3-time Gold Glove winner. Hit .245 but played elite defense."
        },
        {
            "name": "Ozzie Smith (late career)",
            "position": "SS",
            "years": "1978-1996",
            "peak_stats": "6 HR, 50 RBI (1987)",
            "contact": 65, "power": 20, "run": 60, "field": 85, "arm": 80,
            "description": "Wizard with the glove in his later years. Declining bat, elite defense.",
            "career_summary": "15-time Gold Glove winner. Hit .262 with exceptional defensive range."
        },
        {
            "name": "Royce Clayton",
            "position": "SS",
            "years": "1991-2007",
            "peak_stats": "14 HR, 61 RBI (2001)",
            "contact": 55, "power": 35, "run": 55, "field": 75, "arm": 75,
            "description": "Solid defensive shortstop with limited offensive production. Consistent glove.",
            "career_summary": "Career .258 hitter with 98 HRs. Durable defensive shortstop over 17 seasons."
        },
        {
            "name": "Neifi Perez",
            "position": "SS",
            "years": "1996-2007",
            "peak_stats": "12 HR, 59 RBI (2000)",
            "contact": 60, "power": 30, "run": 50, "field": 75, "arm": 70,
            "description": "Flashy glove with no plate discipline. Free swinger with occasional gap pop.",
            "career_summary": "Career .267 hitter with poor OBP. Gold Glove-caliber defender."
        },
    ],

    # Power-hitting shortstops
    "power_ss": [
        {
            "name": "Alex Rodriguez",
            "position": "SS",
            "years": "1994-2013",
            "peak_stats": "54 HR, 156 RBI (2007)",
            "contact": 65, "power": 80, "run": 60, "field": 70, "arm": 75,
            "description": "Superstar shortstop with rare power for position. Athletic and mobile.",
            "career_summary": "696 HRs, 14x All-Star, 3x MVP. Elite power at SS."
        },
        {
            "name": "Nomar Garciaparra",
            "position": "SS",
            "years": "1996-2009",
            "peak_stats": "35 HR, 120 RBI (1997)",
            "contact": 70, "power": 70, "run": 55, "field": 70, "arm": 75,
            "description": "Exceptional hitter for shortstop. Left-handed power threat with good average.",
            "career_summary": "229 HRs with .313 career average. Excellent contact hitter."
        },
        {
            "name": "Miguel Tejada",
            "position": "SS",
            "years": "1997-2013",
            "peak_stats": "34 HR, 131 RBI (2000)",
            "contact": 70, "power": 70, "run": 50, "field": 65, "arm": 75,
            "description": "Offensively-gifted shortstop. Good power and average but average defense.",
            "career_summary": "307 HRs with .291 average. MVP-caliber bat at SS."
        },
        {
            "name": "Hanley Ramirez",
            "position": "SS",
            "years": "2005-2019",
            "peak_stats": "33 HR, 81 RBI (2008)",
            "contact": 65, "power": 70, "run": 70, "field": 55, "arm": 65,
            "description": "Dynamic offensive shortstop with power-speed combo. Defense inconsistent.",
            "career_summary": "271 HRs with .290 average. Two-time batting champion at SS."
        },
        {
            "name": "Troy Tulowitzki",
            "position": "SS",
            "years": "2006-2019",
            "peak_stats": "32 HR, 92 RBI (2010)",
            "contact": 65, "power": 70, "run": 50, "field": 70, "arm": 75,
            "description": "Complete shortstop with plus power and solid glove. Injury-prone but elite when healthy.",
            "career_summary": "225 HRs with .290 average. Five-time All-Star, two Gold Gloves."
        },
    ],

    # Complete catchers
    "complete_catcher": [
        {
            "name": "Mike Piazza",
            "position": "C",
            "years": "1992-2007",
            "peak_stats": "40 HR, 124 RBI (1997)",
            "contact": 70, "power": 80, "run": 40, "field": 45, "arm": 55,
            "description": "Hitting machine behind the plate. Great bat control, limited defense.",
            "career_summary": "427 HRs, greatest offensive catcher ever. Hit .308 lifetime."
        },
        {
            "name": "Ivan Rodriguez",
            "position": "C",
            "years": "1991-2011",
            "peak_stats": "35 HR, 113 RBI (1999)",
            "contact": 70, "power": 70, "run": 50, "field": 75, "arm": 80,
            "description": "All-around excellence at catcher. Great defender, excellent hitter.",
            "career_summary": "311 HRs, 14x All-Star, MVP winner. Elite defense and game-calling."
        },
        {
            "name": "Jorge Posada",
            "position": "C/DH",
            "years": "1995-2011",
            "peak_stats": "42 HR, 124 RBI (2003)",
            "contact": 65, "power": 70, "run": 40, "field": 65, "arm": 70,
            "description": "Yankees catcher with excellent bat and solid defense. Good at handling staff.",
            "career_summary": "275 HRs with .269 average. Switch-hitter, clutch performer."
        },
        {
            "name": "Jason Varitek",
            "position": "C",
            "years": "1997-2011",
            "peak_stats": "25 HR, 85 RBI (2003)",
            "contact": 55, "power": 60, "run": 35, "field": 70, "arm": 70,
            "description": "Outstanding game-caller with solid defense. Modest bat but leadership value.",
            "career_summary": "193 HRs with .256 average. Three-time All-Star, Gold Glove winner."
        },
        {
            "name": "Joe Mauer",
            "position": "C",
            "years": "2004-2018",
            "peak_stats": "28 HR, 96 RBI (2009)",
            "contact": 80, "power": 55, "run": 45, "field": 70, "arm": 65,
            "description": "Elite contact-hitting catcher with batting titles. Plus defender with great receiving skills.",
            "career_summary": "143 HRs with .306 average. MVP winner, three batting titles."
        },
    ],

    # Utility/defense-first players
    "utility_defense": [
        {
            "name": "Mark McLemore",
            "position": "IF/OF",
            "years": "1986-2003",
            "peak_stats": "8 HR, 45 RBI (1999)",
            "contact": 60, "power": 25, "run": 60, "field": 70, "arm": 65,
            "description": "Versatile defender and solid baserunner. Limited bat, useful bench player.",
            "career_summary": "Career .252 hitter with solid defense across multiple positions."
        },
        {
            "name": "Craig Counsell",
            "position": "SS/2B/3B",
            "years": "1994-2011",
            "peak_stats": "8 HR, 50 RBI (2001)",
            "contact": 60, "power": 25, "run": 50, "field": 70, "arm": 70,
            "description": "Super-utility guy. Multiple defensive positions, weak bat but smart player.",
            "career_summary": "Career .245 hitter, excellent defender. Pitched in 2001 World Series."
        },
        {
            "name": "David Eckstein",
            "position": "SS/2B",
            "years": "2001-2011",
            "peak_stats": "8 HR, 62 RBI (2006)",
            "contact": 65, "power": 30, "run": 50, "field": 70, "arm": 65,
            "description": "Scrappy shortstop with good instincts. Limited bat, reliable defender.",
            "career_summary": "World Series MVP in 2006. Hit .266 with solid defense."
        },
        {
            "name": "Tony Phillips",
            "position": "2B/3B/OF",
            "years": "1982-1999",
            "peak_stats": "19 HR, 61 RBI (1992)",
            "contact": 60, "power": 40, "run": 55, "field": 65, "arm": 60,
            "description": "Ultimate super-utility player. Played six positions competently. Good OBP.",
            "career_summary": "Career .266 hitter with excellent walk rate. Versatile defender for 18 seasons."
        },
        {
            "name": "Placido Polanco",
            "position": "2B/3B",
            "years": "1998-2013",
            "peak_stats": "14 HR, 58 RBI (2007)",
            "contact": 70, "power": 35, "run": 45, "field": 75, "arm": 65,
            "description": "High-contact infielder with excellent glove. Rarely struck out, minimal power.",
            "career_summary": "Career .297 hitter with three Gold Gloves. Elite contact rate."
        },
    ],

    # Patient OBP machines
    "obp_machine": [
        {
            "name": "Jason Giambi",
            "position": "1B/DH",
            "years": "1995-2014",
            "peak_stats": "47 HR, 137 RBI (2000)",
            "contact": 65, "power": 75, "run": 40, "field": 40, "arm": 40,
            "description": "Excellent plate discipline with good power. High walk rate, decent average.",
            "career_summary": "441 HRs with .982 OPS lifetime. MVP with outstanding BB/K ratio."
        },
        {
            "name": "Bobby Abreu",
            "position": "RF/LF",
            "years": "1996-2014",
            "peak_stats": "34 HR, 118 RBI (2004)",
            "contact": 70, "power": 65, "run": 70, "field": 65, "arm": 70,
            "description": "Excellent all-around outfielder. Good speed, power, and plate discipline.",
            "career_summary": "288 HRs with .982 OPS. Consistent 30-HR, 100-RBI threat."
        },
        {
            "name": "Todd Helton",
            "position": "1B/OF",
            "years": "1997-2013",
            "peak_stats": "49 HR, 146 RBI (2000)",
            "contact": 75, "power": 75, "run": 50, "field": 65, "arm": 65,
            "description": "Rockies great with excellent contact and power. High average, good walk rate.",
            "career_summary": "369 HRs with .315 career average. Elite OPS with 2,519 hits."
        },
        {
            "name": "John Olerud",
            "position": "1B",
            "years": "1989-2005",
            "peak_stats": "24 HR, 102 RBI (1993)",
            "contact": 75, "power": 60, "run": 35, "field": 65, "arm": 50,
            "description": "Patient lefty hitter with excellent OBP. Hit .363 in 1993. Smooth defender.",
            "career_summary": "255 HRs with .295 average. Career .398 OBP. Three Gold Gloves."
        },
        {
            "name": "Lance Berkman",
            "position": "1B/OF",
            "years": "1999-2013",
            "peak_stats": "45 HR, 136 RBI (2006)",
            "contact": 65, "power": 75, "run": 45, "field": 50, "arm": 55,
            "description": "Switch-hitting slugger with elite plate discipline. Great walk rate and power.",
            "career_summary": "366 HRs with .293 average. Career .406 OBP. Six-time All-Star."
        },
    ],

    # Additional position archetypes
    "high_avg_1b": [
        {
            "name": "Paul Molitor",
            "position": "DH/1B",
            "years": "1978-1998",
            "peak_stats": "19 HR, 88 RBI (1990)",
            "contact": 80, "power": 55, "run": 50, "field": 45, "arm": 45,
            "description": "Hall of Famer with elite contact skills. High average, gap hitter.",
            "career_summary": "3,319 hits with .306 average. Clutch performer in playoffs."
        },
        {
            "name": "Edgar Martinez",
            "position": "DH/1B",
            "years": "1987-2004",
            "peak_stats": "28 HR, 116 RBI (1995)",
            "contact": 75, "power": 70, "run": 40, "field": 45, "arm": 40,
            "description": "Lefty DH extraordinaire. Excellent bat control and power. Hit for average.",
            "career_summary": "309 HRs with .312 average. Top DH of his era."
        },
        {
            "name": "Mark Grace",
            "position": "1B",
            "years": "1988-2003",
            "peak_stats": "14 HR, 98 RBI (1995)",
            "contact": 75, "power": 45, "run": 40, "field": 70, "arm": 55,
            "description": "Line-drive lefty hitter with excellent contact. Led league in hits in the 1990s.",
            "career_summary": "2,445 hits with .303 average. Most hits of any player in the 1990s."
        },
        {
            "name": "Keith Hernandez (late career)",
            "position": "1B",
            "years": "1974-1990",
            "peak_stats": "15 HR, 91 RBI (1979)",
            "contact": 75, "power": 50, "run": 40, "field": 80, "arm": 60,
            "description": "Elite defensive first baseman with high contact skills. Outstanding fielder at 1B.",
            "career_summary": "Career .296 hitter with 11 Gold Gloves. Revolutionized 1B defense."
        },
        {
            "name": "John Kruk",
            "position": "1B/OF",
            "years": "1986-1995",
            "peak_stats": "21 HR, 92 RBI (1991)",
            "contact": 75, "power": 55, "run": 35, "field": 40, "arm": 40,
            "description": "High-average hitter with gap power and great eye. Excellent OBP, limited defense.",
            "career_summary": "Career .300 hitter with .367 OBP. Three-time All-Star."
        },
    ],

    # Athletic outfielders with balanced tools
    "athletic_of": [
        {
            "name": "Bernie Williams",
            "position": "CF",
            "years": "1991-2006",
            "peak_stats": "30 HR, 121 RBI (2000)",
            "contact": 70, "power": 65, "run": 65, "field": 70, "arm": 60,
            "description": "Switch-hitting center fielder with balanced tools. Good power and speed combo.",
            "career_summary": "287 HRs with .297 average. 5x All-Star, 4x Gold Glove winner."
        },
        {
            "name": "Carlos Beltran",
            "position": "CF",
            "years": "1998-2017",
            "peak_stats": "38 HR, 104 RBI (2006)",
            "contact": 65, "power": 70, "run": 70, "field": 75, "arm": 70,
            "description": "Elite switch-hitter with power-speed combo. Excellent defensive center fielder.",
            "career_summary": "435 HRs with 312 SB. 9x All-Star, 3x Gold Glove winner."
        },
        {
            "name": "Larry Walker",
            "position": "RF",
            "years": "1989-2005",
            "peak_stats": "49 HR, 130 RBI (1997)",
            "contact": 70, "power": 70, "run": 60, "field": 75, "arm": 75,
            "description": "Outstanding all-around outfielder. Excellent arm, good power and average.",
            "career_summary": "383 HRs with .313 average. MVP winner, 7x Gold Glove winner."
        },
        {
            "name": "Vladimir Guerrero",
            "position": "RF",
            "years": "1996-2011",
            "peak_stats": "44 HR, 131 RBI (2000)",
            "contact": 70, "power": 75, "run": 60, "field": 65, "arm": 80,
            "description": "Aggressive free-swinger with elite arm strength. Could hit any pitch for power.",
            "career_summary": "449 HRs with .318 average. MVP winner, Hall of Famer."
        },
        {
            "name": "Andre Dawson",
            "position": "RF/CF",
            "years": "1976-1996",
            "peak_stats": "49 HR, 137 RBI (1987)",
            "contact": 60, "power": 70, "run": 60, "field": 70, "arm": 75,
            "description": "Athletic outfielder with power, speed, and cannon arm. Bad knees sapped speed later in career.",
            "career_summary": "438 HRs with .279 average. MVP winner, Hall of Famer."
        },
        {
            "name": "Shawn Green",
            "position": "RF",
            "years": "1993-2007",
            "peak_stats": "49 HR, 125 RBI (2001)",
            "contact": 65, "power": 65, "run": 55, "field": 65, "arm": 60,
            "description": "Well-rounded left-handed outfielder with power surge in middle of career. Smooth swing.",
            "career_summary": "328 HRs with .283 average. 4-HR game in 2002."
        },
    ],

    # Balanced infielders (2B/3B with well-rounded tools)
    "balanced_infielder": [
        {
            "name": "Roberto Alomar",
            "position": "2B",
            "years": "1988-2004",
            "peak_stats": "24 HR, 120 RBI (1999)",
            "contact": 75, "power": 55, "run": 65, "field": 80, "arm": 70,
            "description": "Elite second baseman with excellent bat and glove. Switch-hitter with gap power.",
            "career_summary": "210 HRs with .300 average. 12x All-Star, 10x Gold Glove winner."
        },
        {
            "name": "Jeff Kent",
            "position": "2B",
            "years": "1992-2008",
            "peak_stats": "33 HR, 125 RBI (2000)",
            "contact": 65, "power": 70, "run": 40, "field": 60, "arm": 60,
            "description": "Power-hitting second baseman. Unusual pop for position, solid defender.",
            "career_summary": "377 HRs with .290 average. MVP winner, most HRs by a 2B."
        },
        {
            "name": "Scott Rolen",
            "position": "3B",
            "years": "1996-2012",
            "peak_stats": "31 HR, 110 RBI (2004)",
            "contact": 60, "power": 65, "run": 50, "field": 80, "arm": 75,
            "description": "Elite defensive third baseman with solid bat. Gold Glove caliber.",
            "career_summary": "316 HRs with .281 average. 8x Gold Glove winner, Hall of Famer."
        },
        {
            "name": "Chipper Jones",
            "position": "3B",
            "years": "1993-2012",
            "peak_stats": "45 HR, 128 RBI (1999)",
            "contact": 70, "power": 70, "run": 55, "field": 65, "arm": 70,
            "description": "Switch-hitting third baseman with elite bat. Complete offensive player.",
            "career_summary": "468 HRs with .303 average. MVP winner, Hall of Famer."
        },
        {
            "name": "Robin Ventura",
            "position": "3B",
            "years": "1989-2004",
            "peak_stats": "34 HR, 105 RBI (1996)",
            "contact": 60, "power": 60, "run": 40, "field": 75, "arm": 70,
            "description": "Smooth-fielding third baseman with steady power production. Excellent glove and solid bat.",
            "career_summary": "294 HRs with .267 average. 6x Gold Glove winner."
        },
        {
            "name": "Chase Utley",
            "position": "2B",
            "years": "2003-2018",
            "peak_stats": "33 HR, 104 RBI (2008)",
            "contact": 60, "power": 65, "run": 55, "field": 70, "arm": 65,
            "description": "Hard-nosed second baseman with power and defensive excellence. Physical, aggressive player.",
            "career_summary": "259 HRs with .275 average. 6x All-Star. Elite at 2B."
        },
    ],

    "low_ceiling_backup": [
        {
            "name": "Mark Bellhorn",
            "position": "2B",
            "years": "1997-2007",
            "peak_stats": "17 HR, 62 RBI (2004)",
            "contact": 45, "power": 55, "run": 45, "field": 60, "arm": 55,
            "description": "Limited backup infielder. Streaky power, high strikeout rate.",
            "career_summary": "Career .245 hitter with 99 HRs in 11 seasons. Backup-caliber player."
        },
        {
            "name": "Neifi Perez",
            "position": "SS/2B",
            "years": "1996-2006",
            "peak_stats": "15 HR, 65 RBI (2000)",
            "contact": 50, "power": 45, "run": 50, "field": 60, "arm": 65,
            "description": "Reserve infielder with limited bat skills. Average defender.",
            "career_summary": "Career .258 hitter. Solid defender but weak offensive profile."
        },
        {
            "name": "Rey Sanchez",
            "position": "SS/2B",
            "years": "1990-2001",
            "peak_stats": "2 HR, 28 RBI (1996)",
            "contact": 60, "power": 20, "run": 45, "field": 70, "arm": 65,
            "description": "Light-hitting utility shortstop. Good glove, minimal offensive value.",
            "career_summary": "Career .250 hitter with 32 HRs. Defensive specialist."
        },
        {
            "name": "Willie Bloomquist",
            "position": "IF/OF",
            "years": "2002-2015",
            "peak_stats": "3 HR, 31 RBI (2009)",
            "contact": 55, "power": 20, "run": 55, "field": 60, "arm": 55,
            "description": "Jack-of-all-trades utility man. Could play anywhere but lacked impact bat.",
            "career_summary": "Career .268 hitter with 14 HRs in 14 seasons. Versatile reserve."
        },
        {
            "name": "Ramon Santiago",
            "position": "SS/2B",
            "years": "2002-2014",
            "peak_stats": "5 HR, 33 RBI (2012)",
            "contact": 50, "power": 25, "run": 50, "field": 65, "arm": 65,
            "description": "Defensive-minded middle infielder. Light bat with occasional gap power.",
            "career_summary": "Career .242 hitter. Solid utility infielder for 13 seasons."
        },
    ],

    # Power-hitting outfielders
    "power_of": [
        {
            "name": "Sammy Sosa",
            "position": "RF",
            "years": "1989-2007",
            "peak_stats": "66 HR, 158 RBI (1998)",
            "contact": 55, "power": 80, "run": 60, "field": 55, "arm": 70,
            "description": "Explosive power with aggressive approach. Free swinger who could carry a team with home runs.",
            "career_summary": "609 HRs with .273 average. 7x All-Star, MVP winner. Three 60-HR seasons."
        },
        {
            "name": "Manny Ramirez",
            "position": "LF",
            "years": "1993-2011",
            "peak_stats": "45 HR, 144 RBI (1999)",
            "contact": 70, "power": 80, "run": 40, "field": 35, "arm": 55,
            "description": "One of the purest right-handed hitters ever. Elite bat speed and pitch recognition. Poor defender.",
            "career_summary": "555 HRs with .312 average. 12x All-Star. Career .996 OPS."
        },
        {
            "name": "Gary Sheffield",
            "position": "RF/LF",
            "years": "1988-2009",
            "peak_stats": "43 HR, 134 RBI (2003)",
            "contact": 65, "power": 75, "run": 55, "field": 45, "arm": 65,
            "description": "Intimidating bat waggle with quick hands and tremendous bat speed. Aggressive hitter.",
            "career_summary": "509 HRs with .292 average. 9x All-Star. Consistent 30+ HR threat."
        },
        {
            "name": "J.D. Drew",
            "position": "RF",
            "years": "1998-2011",
            "peak_stats": "31 HR, 93 RBI (2004)",
            "contact": 60, "power": 65, "run": 55, "field": 65, "arm": 65,
            "description": "Patient hitter with plus power and solid defense. Often criticized for lack of intensity despite elite tools.",
            "career_summary": "242 HRs with .278 average. Career .386 OBP. Injury-prone but productive."
        },
        {
            "name": "Adam Dunn",
            "position": "LF/1B",
            "years": "2001-2014",
            "peak_stats": "46 HR, 102 RBI (2004)",
            "contact": 35, "power": 80, "run": 40, "field": 30, "arm": 50,
            "description": "Three true outcomes hitter. Homer, walk, or strikeout. Historically high K rate with elite power.",
            "career_summary": "462 HRs with .237 average. Led league in strikeouts 7 times."
        },
        {
            "name": "Jim Rice",
            "position": "LF",
            "years": "1974-1989",
            "peak_stats": "46 HR, 139 RBI (1978)",
            "contact": 60, "power": 75, "run": 50, "field": 50, "arm": 60,
            "description": "Feared power hitter with line-drive power to all fields. Physical left fielder with plus arm.",
            "career_summary": "382 HRs with .298 average. MVP winner, Hall of Famer."
        },
        {
            "name": "Darryl Strawberry",
            "position": "RF",
            "years": "1983-1999",
            "peak_stats": "39 HR, 104 RBI (1987)",
            "contact": 50, "power": 80, "run": 60, "field": 55, "arm": 70,
            "description": "Towering power from left side with long, leveraged swing. Athletic with speed and arm strength.",
            "career_summary": "335 HRs with .259 average. 8x All-Star. Elite raw power."
        },
        {
            "name": "Jose Canseco",
            "position": "RF/DH",
            "years": "1985-2001",
            "peak_stats": "46 HR, 124 RBI (1998)",
            "contact": 50, "power": 80, "run": 60, "field": 40, "arm": 65,
            "description": "First 40-40 player. Combination of power and speed rare for his size. Aggressive swinger.",
            "career_summary": "462 HRs with .266 average. MVP winner. 200 SB despite size."
        },
    ],

    # Gap hitters / line-drive specialists
    "gap_hitter": [
        {
            "name": "Derek Jeter",
            "position": "SS",
            "years": "1995-2014",
            "peak_stats": "24 HR, 102 RBI (1999)",
            "contact": 75, "power": 55, "run": 60, "field": 55, "arm": 60,
            "description": "Inside-out swing with ability to drive ball to right field. Clutch performer with excellent bat control.",
            "career_summary": "3,465 hits with .310 average. 14x All-Star, 5x World Series champion."
        },
        {
            "name": "Wade Boggs",
            "position": "3B",
            "years": "1982-1999",
            "peak_stats": "24 HR, 89 RBI (1987)",
            "contact": 80, "power": 45, "run": 40, "field": 60, "arm": 60,
            "description": "Elite contact hitter who sprayed line drives. Exceptional eye with career .415 OBP.",
            "career_summary": "3,010 hits with .328 average. 5x batting champion, Hall of Famer."
        },
        {
            "name": "Tony Gwynn",
            "position": "RF",
            "years": "1982-2001",
            "peak_stats": "17 HR, 119 RBI (1997)",
            "contact": 80, "power": 40, "run": 55, "field": 60, "arm": 60,
            "description": "Greatest pure hitter of his generation. Phenomenal bat control, rarely struck out.",
            "career_summary": "3,141 hits with .338 average. 8x batting champion, Hall of Famer."
        },
        {
            "name": "Rod Carew (late career)",
            "position": "1B/DH",
            "years": "1967-1985",
            "peak_stats": "14 HR, 100 RBI (1977)",
            "contact": 80, "power": 35, "run": 55, "field": 55, "arm": 50,
            "description": "Bat magician who could place hits anywhere. Later career saw declining speed but maintained contact mastery.",
            "career_summary": "3,053 hits with .328 average. 18x All-Star, 7x batting champion."
        },
        {
            "name": "Don Mattingly",
            "position": "1B",
            "years": "1982-1995",
            "peak_stats": "35 HR, 145 RBI (1985)",
            "contact": 75, "power": 60, "run": 40, "field": 75, "arm": 60,
            "description": "Line-drive machine with gap power and Gold Glove defense. Back injuries sapped power in later years.",
            "career_summary": "222 HRs with .307 average. MVP winner, 9x Gold Glove at 1B."
        },
        {
            "name": "Kirby Puckett",
            "position": "CF",
            "years": "1984-1995",
            "peak_stats": "31 HR, 114 RBI (1988)",
            "contact": 75, "power": 60, "run": 55, "field": 70, "arm": 65,
            "description": "Barrel-chested contact machine who hit line drives to all fields. Excellent outfielder with plus instincts.",
            "career_summary": "207 HRs with .318 average. 10x All-Star, Hall of Famer."
        },
        {
            "name": "Will Clark",
            "position": "1B",
            "years": "1986-2000",
            "peak_stats": "29 HR, 116 RBI (1991)",
            "contact": 75, "power": 60, "run": 45, "field": 70, "arm": 60,
            "description": "Sweet left-handed swing with natural gap power. Outstanding hitter's approach and excellent first baseman.",
            "career_summary": "284 HRs with .303 average. 6x All-Star. Career .384 OBP."
        },
    ],

    # Classic leadoff men
    "leadoff_specialist": [
        {
            "name": "Rickey Henderson",
            "position": "LF",
            "years": "1979-2003",
            "peak_stats": "28 HR, 74 RBI (1990)",
            "contact": 60, "power": 50, "run": 80, "field": 60, "arm": 55,
            "description": "Greatest leadoff hitter ever. Elite speed, patience, and power for a leadoff man. Changed the game.",
            "career_summary": "3,055 hits, 1,406 SB, .401 OBP. 10x All-Star, Hall of Famer."
        },
        {
            "name": "Tim Raines",
            "position": "LF",
            "years": "1979-2002",
            "peak_stats": "18 HR, 68 RBI (1987)",
            "contact": 70, "power": 40, "run": 80, "field": 60, "arm": 55,
            "description": "Elite contact-speed combo with excellent OBP. One of the best base stealers ever at 87% success rate.",
            "career_summary": "2,605 hits with .294 average. 808 SB, Hall of Famer."
        },
        {
            "name": "Craig Biggio",
            "position": "2B/CF",
            "years": "1988-2007",
            "peak_stats": "24 HR, 81 RBI (1998)",
            "contact": 65, "power": 50, "run": 65, "field": 65, "arm": 60,
            "description": "Versatile leadoff man who transitioned from catcher to second base. Excellent OBP with gap power.",
            "career_summary": "3,060 hits with .281 average. 414 SB, Hall of Famer."
        },
        {
            "name": "Brian Roberts",
            "position": "2B",
            "years": "2001-2013",
            "peak_stats": "12 HR, 57 RBI (2005)",
            "contact": 65, "power": 40, "run": 65, "field": 65, "arm": 60,
            "description": "Switch-hitting leadoff man with gap power and base-stealing ability. Good plate discipline.",
            "career_summary": "Career .277 hitter with 264 SB. 2x All-Star."
        },
        {
            "name": "Brett Butler",
            "position": "CF",
            "years": "1981-1997",
            "peak_stats": "9 HR, 44 RBI (1991)",
            "contact": 70, "power": 25, "run": 75, "field": 70, "arm": 50,
            "description": "Classic old-school leadoff man. Bunted for hits, walked, stole bases, and played solid center field.",
            "career_summary": "2,375 hits with .290 average. 558 SB. Career .377 OBP."
        },
        {
            "name": "Vince Coleman",
            "position": "LF",
            "years": "1985-1997",
            "peak_stats": "3 HR, 43 RBI (1987)",
            "contact": 55, "power": 20, "run": 80, "field": 50, "arm": 50,
            "description": "Blazing speed as primary weapon. Limited bat and defense but could single-handedly disrupt games on the bases.",
            "career_summary": "Career .264 hitter with 752 SB. Three consecutive 100-SB seasons."
        },
    ],

    # Power second basemen
    "power_2b": [
        {
            "name": "Jeff Kent",
            "position": "2B",
            "years": "1992-2008",
            "peak_stats": "33 HR, 125 RBI (2000)",
            "contact": 65, "power": 70, "run": 40, "field": 55, "arm": 60,
            "description": "Rare power for second base position. RBI machine with line-drive power to gaps and over fence.",
            "career_summary": "377 HRs with .290 average. MVP winner, most HRs by a 2B ever."
        },
        {
            "name": "Alfonso Soriano",
            "position": "2B/LF",
            "years": "1999-2014",
            "peak_stats": "46 HR, 95 RBI (2006)",
            "contact": 55, "power": 75, "run": 70, "field": 45, "arm": 60,
            "description": "Explosive athlete with rare power-speed combo at second base. Aggressive hacker with big swing.",
            "career_summary": "412 HRs with .270 average. 4x 40-HR seasons. Only member of 40-40 club at 2B."
        },
        {
            "name": "Robinson Cano",
            "position": "2B",
            "years": "2005-2020",
            "peak_stats": "33 HR, 118 RBI (2016)",
            "contact": 70, "power": 65, "run": 50, "field": 70, "arm": 65,
            "description": "Smooth, effortless left-handed swing. Natural hitter with plus power for position and excellent glovework.",
            "career_summary": "335 HRs with .302 average. 8x All-Star, 2x Gold Glove winner."
        },
        {
            "name": "Dan Uggla",
            "position": "2B",
            "years": "2006-2014",
            "peak_stats": "33 HR, 105 RBI (2010)",
            "contact": 45, "power": 70, "run": 40, "field": 45, "arm": 55,
            "description": "All-or-nothing power hitter at second base. High strikeout rate offset by significant home run totals.",
            "career_summary": "169 HRs with .241 average. 3x All-Star. Pure power at 2B."
        },
        {
            "name": "Bret Boone",
            "position": "2B",
            "years": "1992-2005",
            "peak_stats": "37 HR, 141 RBI (2001)",
            "contact": 60, "power": 65, "run": 45, "field": 65, "arm": 65,
            "description": "Muscular second baseman who developed power in his prime. Solid defender with surprising pop.",
            "career_summary": "252 HRs with .266 average. 3x All-Star, 4x Gold Glove winner."
        },
    ],

    # Power third basemen
    "power_3b": [
        {
            "name": "Mike Schmidt (late career)",
            "position": "3B",
            "years": "1972-1989",
            "peak_stats": "48 HR, 121 RBI (1980)",
            "contact": 55, "power": 80, "run": 45, "field": 75, "arm": 75,
            "description": "Greatest third baseman ever in his later years. Still elite power and defense, declining speed.",
            "career_summary": "548 HRs with .267 average. 3x MVP, 10x Gold Glove. Hall of Famer."
        },
        {
            "name": "Chipper Jones",
            "position": "3B",
            "years": "1993-2012",
            "peak_stats": "45 HR, 128 RBI (1999)",
            "contact": 70, "power": 70, "run": 55, "field": 60, "arm": 65,
            "description": "Switch-hitting superstar with elite bat from both sides. Rare combination of average and power at third.",
            "career_summary": "468 HRs with .303 average. MVP winner, Hall of Famer."
        },
        {
            "name": "Aramis Ramirez",
            "position": "3B",
            "years": "1998-2015",
            "peak_stats": "38 HR, 112 RBI (2004)",
            "contact": 65, "power": 65, "run": 35, "field": 55, "arm": 60,
            "description": "Quiet, consistent run producer with gap-to-gap power. Smooth swing and solid bat-to-ball skills.",
            "career_summary": "386 HRs with .283 average. 3x All-Star. Consistent 25+ HR threat."
        },
        {
            "name": "Adrian Beltre",
            "position": "3B",
            "years": "1998-2018",
            "peak_stats": "48 HR, 121 RBI (2004)",
            "contact": 65, "power": 70, "run": 50, "field": 75, "arm": 70,
            "description": "Elite two-way third baseman with power and plus defense. Unconventional swing with extreme bat speed.",
            "career_summary": "477 HRs with .286 average. 4x All-Star, 5x Gold Glove. 3,166 hits."
        },
        {
            "name": "Evan Longoria",
            "position": "3B",
            "years": "2008-2022",
            "peak_stats": "33 HR, 113 RBI (2009)",
            "contact": 55, "power": 65, "run": 45, "field": 70, "arm": 70,
            "description": "Well-rounded third baseman with plus defense and steady power. Good strike-zone judgment.",
            "career_summary": "305 HRs with .262 average. 3x All-Star, 3x Gold Glove winner."
        },
        {
            "name": "Troy Glaus",
            "position": "3B",
            "years": "1998-2010",
            "peak_stats": "47 HR, 108 RBI (2000)",
            "contact": 45, "power": 75, "run": 40, "field": 55, "arm": 65,
            "description": "Raw power hitter with big swing and high strikeout rate. Pull-heavy approach with massive home runs.",
            "career_summary": "320 HRs with .254 average. World Series MVP in 2002."
        },
    ],

    # Gold Glove outfielders (defense-first)
    "defensive_of": [
        {
            "name": "Devon White",
            "position": "CF",
            "years": "1985-2001",
            "peak_stats": "17 HR, 60 RBI (1991)",
            "contact": 55, "power": 45, "run": 75, "field": 80, "arm": 65,
            "description": "Spectacular defensive center fielder with range and athleticism. Gap power and speed.",
            "career_summary": "208 HRs with .263 average. 7x Gold Glove winner."
        },
        {
            "name": "Marquis Grissom",
            "position": "CF",
            "years": "1989-2005",
            "peak_stats": "22 HR, 76 RBI (1997)",
            "contact": 60, "power": 45, "run": 70, "field": 75, "arm": 60,
            "description": "Athletic center fielder with good speed and defense. Contact-oriented bat with limited patience.",
            "career_summary": "227 HRs with .272 average. 4x Gold Glove winner, 429 SB."
        },
        {
            "name": "Eric Davis",
            "position": "CF",
            "years": "1984-2001",
            "peak_stats": "37 HR, 100 RBI (1987)",
            "contact": 50, "power": 65, "run": 75, "field": 80, "arm": 70,
            "description": "Electrifying athlete with power-speed combo and elite center field defense. Injury-plagued career.",
            "career_summary": "282 HRs with .269 average. Potential five-tool star limited by injuries."
        },
        {
            "name": "Jim Edmonds",
            "position": "CF",
            "years": "1993-2010",
            "peak_stats": "42 HR, 111 RBI (2004)",
            "contact": 60, "power": 70, "run": 60, "field": 80, "arm": 70,
            "description": "Breathtaking defensive center fielder with power bat. Known for spectacular diving catches.",
            "career_summary": "393 HRs with .284 average. 8x Gold Glove winner."
        },
        {
            "name": "Curt Flood (concept/late era equivalent)",
            "position": "CF",
            "years": "concept",
            "peak_stats": "N/A",
            "contact": 65, "power": 35, "run": 65, "field": 80, "arm": 65,
            "description": "Prototypical defense-first center fielder archetype. Elite range and instincts.",
            "career_summary": "Archetype for glove-first outfielders who sacrifice bat for defense."
        },
        {
            "name": "Dwayne Murphy",
            "position": "CF",
            "years": "1978-1989",
            "peak_stats": "26 HR, 94 RBI (1984)",
            "contact": 50, "power": 55, "run": 65, "field": 80, "arm": 65,
            "description": "Defensive wizard in center with patient approach. Good walk rate offset low average.",
            "career_summary": "166 HRs with .246 average. 6x Gold Glove winner."
        },
    ],

    # Notable switch hitters
    "switch_hitter": [
        {
            "name": "Mickey Mantle (late career)",
            "position": "CF/1B",
            "years": "1951-1968",
            "peak_stats": "54 HR, 130 RBI (1961)",
            "contact": 55, "power": 75, "run": 50, "field": 50, "arm": 60,
            "description": "Greatest switch-hitter ever in declining years. Still dangerous power from both sides despite bad knees.",
            "career_summary": "536 HRs with .298 average. 3x MVP, Hall of Famer."
        },
        {
            "name": "Bernie Williams",
            "position": "CF",
            "years": "1991-2006",
            "peak_stats": "30 HR, 121 RBI (2000)",
            "contact": 70, "power": 60, "run": 60, "field": 65, "arm": 55,
            "description": "Graceful switch-hitter with balanced offensive game. Good gap power and solid center field defense.",
            "career_summary": "287 HRs with .297 average. 5x All-Star, 4x Gold Glove winner."
        },
        {
            "name": "Lance Berkman",
            "position": "1B/OF",
            "years": "1999-2013",
            "peak_stats": "45 HR, 136 RBI (2006)",
            "contact": 65, "power": 70, "run": 40, "field": 50, "arm": 55,
            "description": "Switch-hitting slugger with elite plate discipline and power from both sides. Better left-handed.",
            "career_summary": "366 HRs with .293 average. Career .406 OBP. 6x All-Star."
        },
        {
            "name": "Victor Martinez",
            "position": "C/DH",
            "years": "2002-2018",
            "peak_stats": "32 HR, 103 RBI (2014)",
            "contact": 75, "power": 55, "run": 30, "field": 50, "arm": 55,
            "description": "Elite contact switch-hitter who rarely struck out. Transitioned from catcher to DH. Pure hitter.",
            "career_summary": "246 HRs with .295 average. 5x All-Star. Career .356 OBP."
        },
        {
            "name": "Carlos Beltran",
            "position": "CF",
            "years": "1998-2017",
            "peak_stats": "38 HR, 104 RBI (2006)",
            "contact": 65, "power": 70, "run": 70, "field": 70, "arm": 65,
            "description": "Complete switch-hitter with five-tool potential. Power-speed threat from both sides of the plate.",
            "career_summary": "435 HRs with .279 average. 312 SB. 9x All-Star."
        },
    ],

    # Career DH specialists
    "dh_specialist": [
        {
            "name": "David Ortiz",
            "position": "DH",
            "years": "1997-2016",
            "peak_stats": "54 HR, 137 RBI (2006)",
            "contact": 60, "power": 80, "run": 25, "field": 25, "arm": 30,
            "description": "Big Papi. Greatest DH ever. Clutch performer with enormous power and presence in the lineup.",
            "career_summary": "541 HRs with .286 average. 10x All-Star, 3x World Series champion."
        },
        {
            "name": "Harold Baines",
            "position": "DH/RF",
            "years": "1980-2001",
            "peak_stats": "29 HR, 113 RBI (1996)",
            "contact": 70, "power": 60, "run": 35, "field": 40, "arm": 55,
            "description": "Smooth left-handed swing with consistent line-drive production. Excellent contact and gap power.",
            "career_summary": "384 HRs with .289 average. 2,866 hits. 6x All-Star."
        },
        {
            "name": "Hal McRae",
            "position": "DH/OF",
            "years": "1968-1987",
            "peak_stats": "27 HR, 133 RBI (1982)",
            "contact": 65, "power": 55, "run": 45, "field": 40, "arm": 50,
            "description": "Pioneer DH who embraced the role. Aggressive, physical hitter with gap power and toughness.",
            "career_summary": "191 HRs with .290 average. 3x All-Star. Defined the DH role."
        },
        {
            "name": "Travis Hafner",
            "position": "DH",
            "years": "2002-2013",
            "peak_stats": "33 HR, 108 RBI (2006)",
            "contact": 60, "power": 70, "run": 25, "field": 25, "arm": 35,
            "description": "Pronk. Patient hitter with tremendous power in his peak years. Shoulder injuries shortened prime.",
            "career_summary": "213 HRs with .273 average. Career .390 OBP. Dominant 2005-2006."
        },
        {
            "name": "Frank Thomas",
            "position": "DH/1B",
            "years": "1990-2008",
            "peak_stats": "42 HR, 128 RBI (2000)",
            "contact": 60, "power": 75, "run": 30, "field": 35, "arm": 40,
            "description": "Big Hurt. Two-time MVP who became a full-time DH later. Elite power and plate discipline.",
            "career_summary": "521 HRs with .301 average. Career .419 OBP. Hall of Famer."
        },
    ],
}


# Pitcher archetypes (1985-2020 era)
PITCHER_COMPS = {
    # Power closers
    "power_closer": [
        {
            "name": "Mariano Rivera",
            "position": "RP",
            "years": "1995-2013",
            "peak_stats": "53 saves, 1.38 ERA (2008)",
            "fastball": 80, "curveball": 50, "slider": 75, "changeup": 50, "command": 85, "control": 85,
            "description": "Greatest closer ever. Cut fastball is signature pitch. Unmatched consistency.",
            "career_summary": "652 saves with 2.21 ERA. 13x All-Star. Incredible durability."
        },
        {
            "name": "Trevor Hoffman",
            "position": "RP",
            "years": "1986-2010",
            "peak_stats": "53 saves, 1.48 ERA (1998)",
            "fastball": 75, "curveball": 60, "slider": 70, "changeup": 55, "command": 80, "control": 80,
            "description": "Elite closer with multiple power pitches. Excellent control.",
            "career_summary": "601 saves with 2.87 ERA. Hall of Famer."
        },
        {
            "name": "Billy Wagner",
            "position": "RP",
            "years": "1995-2010",
            "peak_stats": "47 saves, 1.87 ERA (1997)",
            "fastball": 80, "curveball": 55, "slider": 65, "changeup": 45, "command": 70, "control": 75,
            "description": "Overpowering left-hander. Triple-digit fastball with excellent slider.",
            "career_summary": "422 saves with 2.31 ERA. Dominant stuff, health issues."
        },
        {
            "name": "Eric Gagne",
            "position": "RP",
            "years": "1999-2008",
            "peak_stats": "55 saves, 1.20 ERA (2003)",
            "fastball": 80, "curveball": 70, "slider": 75, "changeup": 60, "command": 80, "control": 80,
            "description": "Phenomenal closer at peak. Dominant stuff and control. Arm issues later.",
            "career_summary": "162 saves with 3.40 ERA. Cy Young winner, injury-plagued later."
        },
    ],

    # Ace starters
    "ace_starter": [
        {
            "name": "Pedro Martinez",
            "position": "SP",
            "years": "1992-2009",
            "peak_stats": "23-4, 1.74 ERA (2000)",
            "fastball": 80, "curveball": 80, "slider": 75, "changeup": 75, "command": 85, "control": 85,
            "description": "Greatest pitcher of his era. Dominant stuff, perfect mechanics.",
            "career_summary": "219 wins with 2.93 ERA. 3x Cy Young, 8x All-Star."
        },
        {
            "name": "Roger Clemens",
            "position": "SP",
            "years": "1984-2007",
            "peak_stats": "24-4, 1.87 ERA (1997)",
            "fastball": 80, "curveball": 75, "slider": 75, "changeup": 70, "command": 80, "control": 80,
            "description": "Dominant power pitcher. Excellent fastball and slider.",
            "career_summary": "354 wins with 3.12 ERA. 7x Cy Young, Hall of Famer."
        },
        {
            "name": "Randy Johnson",
            "position": "SP",
            "years": "1988-2009",
            "peak_stats": "19-7, 2.28 ERA (1999)",
            "fastball": 85, "curveball": 80, "slider": 75, "changeup": 50, "command": 70, "control": 70,
            "description": "Big Unit with overwhelming power. Overpowering fastball and curveball.",
            "career_summary": "303 wins with 3.29 ERA. 4x Cy Young, 10x All-Star."
        },
        {
            "name": "Curt Schilling",
            "position": "SP",
            "years": "1988-2007",
            "peak_stats": "23-8, 2.98 ERA (2004)",
            "fastball": 75, "curveball": 80, "slider": 80, "changeup": 70, "command": 75, "control": 75,
            "description": "Excellent control with plus-plus curveball. Gritty competitor.",
            "career_summary": "216 wins with 3.46 ERA. Postseason ace."
        },
    ],

    # Finesse starters
    "finesse_starter": [
        {
            "name": "Greg Maddux",
            "position": "SP",
            "years": "1986-2008",
            "peak_stats": "22-6, 1.56 ERA (1994)",
            "fastball": 70, "curveball": 75, "slider": 75, "changeup": 75, "command": 90, "control": 90,
            "description": "Master of pitching. Perfect control and movement. Minimal walks.",
            "career_summary": "355 wins with 3.16 ERA. 4x Cy Young, Hall of Famer."
        },
        {
            "name": "Tom Glavine",
            "position": "SP",
            "years": "1987-2008",
            "peak_stats": "24-8, 2.36 ERA (1993)",
            "fastball": 70, "curveball": 75, "slider": 70, "changeup": 75, "command": 85, "control": 85,
            "description": "Pinpoint control with excellent changeup. Left-handed master.",
            "career_summary": "305 wins with 3.54 ERA. 2x Cy Young, Hall of Famer."
        },
        {
            "name": "Jamie Moyer",
            "position": "SP",
            "years": "1986-2012",
            "peak_stats": "21-7, 3.43 ERA (2001)",
            "fastball": 60, "curveball": 70, "slider": 65, "changeup": 75, "command": 85, "control": 85,
            "description": "Finesse left-hander with excellent changeup. Remarkable longevity.",
            "career_summary": "269 wins with 3.74 ERA. Pitched into his 40s."
        },
        {
            "name": "Mike Mussina",
            "position": "SP",
            "years": "1991-2008",
            "peak_stats": "19-11, 3.20 ERA (1995)",
            "fastball": 70, "curveball": 75, "slider": 65, "changeup": 70, "command": 80, "control": 80,
            "description": "Cerebral pitcher with plus knuckle-curve and pinpoint location. Evolved from power to finesse.",
            "career_summary": "270 wins with 3.68 ERA. 5x All-Star, Hall of Famer."
        },
        {
            "name": "John Smoltz (as starter)",
            "position": "SP",
            "years": "1988-2009",
            "peak_stats": "24-8, 2.94 ERA (1996)",
            "fastball": 75, "curveball": 70, "slider": 80, "changeup": 65, "command": 75, "control": 75,
            "description": "Power-finesse hybrid with elite slider. Unique career as both dominant starter and closer.",
            "career_summary": "213 wins, 154 saves with 3.33 ERA. Cy Young winner, Hall of Famer."
        },
    ],

    # Innings eaters
    "innings_eater": [
        {
            "name": "Livan Hernandez",
            "position": "SP",
            "years": "1996-2012",
            "peak_stats": "17-12, 3.42 ERA (1997)",
            "fastball": 70, "curveball": 65, "slider": 65, "changeup": 65, "command": 70, "control": 70,
            "description": "Durable starter who eats innings. Good movement, average stuff.",
            "career_summary": "245 wins. Reliable innings producer for 17 seasons."
        },
        {
            "name": "Jaime Navarro",
            "position": "SP",
            "years": "1989-2000",
            "peak_stats": "17-11, 3.28 ERA (1994)",
            "fastball": 70, "curveball": 65, "slider": 60, "changeup": 60, "command": 70, "control": 70,
            "description": "Solid fourth/fifth starter. Decent stuff and durability.",
            "career_summary": "125 wins with 4.10 ERA. Workhorse innings pitcher."
        },
        {
            "name": "Kevin Brown",
            "position": "SP",
            "years": "1986-2005",
            "peak_stats": "18-9, 2.28 ERA (1996)",
            "fastball": 70, "curveball": 70, "slider": 70, "changeup": 65, "command": 75, "control": 75,
            "description": "Balanced pitcher with above-average control. Reliable innings.",
            "career_summary": "211 wins with 3.28 ERA. Consistent starter."
        },
        {
            "name": "Chuck Finley",
            "position": "SP",
            "years": "1986-2002",
            "peak_stats": "18-9, 3.15 ERA (1990)",
            "fastball": 70, "curveball": 65, "slider": 65, "changeup": 65, "command": 65, "control": 65,
            "description": "Durable left-hander who logged consistent innings. Solid four-pitch mix without dominant stuff.",
            "career_summary": "200 wins with 3.85 ERA. 5x All-Star. 2,151 strikeouts."
        },
        {
            "name": "Brad Radke",
            "position": "SP",
            "years": "1995-2006",
            "peak_stats": "20-10, 3.48 ERA (1997)",
            "fastball": 65, "curveball": 60, "slider": 65, "changeup": 70, "command": 80, "control": 80,
            "description": "Control artist who pounded the strike zone. Low walk rate compensated for modest stuff.",
            "career_summary": "148 wins with 4.22 ERA. Model of consistency and efficiency."
        },
    ],

    # Strikeout artists
    "strikeout_artist": [
        {
            "name": "Nolan Ryan (late career)",
            "position": "SP",
            "years": "1966-1993",
            "peak_stats": "27-29 W-L at age 45+ (ERA around 3.5)",
            "fastball": 85, "curveball": 70, "slider": 65, "changeup": 50, "command": 55, "control": 55,
            "description": "Express fastball artist. Phenomenal strikeout rate, high walks.",
            "career_summary": "324 wins with 3.19 ERA. 7x K leader, Hall of Famer."
        },
        {
            "name": "Kerry Wood",
            "position": "SP",
            "years": "1998-2012",
            "peak_stats": "14-6, 3.36 ERA (1998), 20 K in game",
            "fastball": 80, "curveball": 80, "slider": 75, "changeup": 60, "command": 70, "control": 70,
            "description": "Power pitcher with plus-plus curveball. Injury-prone.",
            "career_summary": "86 wins with 4.53 ERA. Dominant when healthy."
        },
        {
            "name": "Dwight Gooden",
            "position": "SP",
            "years": "1984-2000",
            "peak_stats": "24-4, 1.53 ERA (1985)",
            "fastball": 80, "curveball": 80, "slider": 65, "changeup": 65, "command": 75, "control": 70,
            "description": "Electrifying young arm with devastating curveball. Overpowering stuff at peak.",
            "career_summary": "194 wins with 3.51 ERA. Cy Young winner at age 20."
        },
        {
            "name": "Hideo Nomo",
            "position": "SP",
            "years": "1995-2008",
            "peak_stats": "16-11, 2.54 ERA (1995)",
            "fastball": 75, "curveball": 50, "slider": 60, "changeup": 55, "command": 60, "control": 55,
            "description": "Tornado windup with devastating forkball. High strikeout rate but prone to walks.",
            "career_summary": "123 wins with 4.24 ERA. Two no-hitters. Pioneer Japanese MLB player."
        },
        {
            "name": "Mark Prior",
            "position": "SP",
            "years": "2002-2006",
            "peak_stats": "18-6, 2.43 ERA (2003)",
            "fastball": 80, "curveball": 75, "slider": 70, "changeup": 60, "command": 70, "control": 70,
            "description": "Textbook mechanics with elite fastball-curveball combo. Injuries derailed Hall of Fame potential.",
            "career_summary": "42 wins with 3.51 ERA. Dominant when healthy, career cut short."
        },
    ],

    # Ground ball specialists
    "ground_ball_sp": [
        {
            "name": "Derek Lowe",
            "position": "SP",
            "years": "1997-2012",
            "peak_stats": "17-7, 3.50 ERA (2002)",
            "fastball": 70, "curveball": 60, "slider": 70, "changeup": 65, "command": 75, "control": 75,
            "description": "Ground ball specialist with excellent slider. Minimal walks.",
            "career_summary": "204 wins with 3.63 ERA. GB pitcher."
        },
        {
            "name": "Brandon Webb",
            "position": "SP",
            "years": "2003-2012",
            "peak_stats": "18-10, 3.30 ERA (2006)",
            "fastball": 75, "curveball": 70, "slider": 75, "changeup": 65, "command": 75, "control": 75,
            "description": "Sinker specialist with excellent control. Ground ball oriented.",
            "career_summary": "87 wins with 3.82 ERA before injuries."
        },
        {
            "name": "Chien-Ming Wang",
            "position": "SP",
            "years": "2005-2016",
            "peak_stats": "19-7, 3.63 ERA (2006)",
            "fastball": 75, "curveball": 55, "slider": 65, "changeup": 55, "command": 70, "control": 70,
            "description": "Heavy sinker that generated extreme ground ball rates. Relied almost entirely on sinking fastball.",
            "career_summary": "54 wins with 4.11 ERA. Elite ground ball rate before foot injury."
        },
        {
            "name": "Jake Westbrook",
            "position": "SP",
            "years": "2000-2013",
            "peak_stats": "15-10, 3.38 ERA (2004)",
            "fastball": 70, "curveball": 60, "slider": 65, "changeup": 60, "command": 70, "control": 70,
            "description": "Classic sinker-slider pitcher who kept the ball on the ground. Durable mid-rotation arm.",
            "career_summary": "99 wins with 4.29 ERA. Consistent ground ball pitcher."
        },
        {
            "name": "Aaron Cook",
            "position": "SP",
            "years": "2002-2012",
            "peak_stats": "16-9, 3.96 ERA (2008)",
            "fastball": 70, "curveball": 55, "slider": 60, "changeup": 55, "command": 65, "control": 65,
            "description": "Extreme ground ball pitcher, especially in Coors Field. Heavy sinker with late movement.",
            "career_summary": "72 wins with 4.53 ERA. Remarkably effective in Colorado."
        },
    ],

    # Middle relievers
    "middle_reliever": [
        {
            "name": "Marty Cordova (as reliever)",
            "position": "RP",
            "years": "Variable",
            "peak_stats": "8 saves, 3.00 ERA",
            "fastball": 75, "curveball": 65, "slider": 65, "changeup": 60, "command": 70, "control": 70,
            "description": "Solid middle reliever. Decent stuff, above-average control.",
            "career_summary": "Multiple innings arm in bullpen."
        },
        {
            "name": "Paul Quantrill",
            "position": "RP",
            "years": "1992-2005",
            "peak_stats": "3.04 ERA, 86 G (2002)",
            "fastball": 65, "curveball": 55, "slider": 60, "changeup": 65, "command": 75, "control": 75,
            "description": "Durable sinker-baller who appeared in huge number of games. Ground ball machine from the pen.",
            "career_summary": "48 wins, 65 saves with 3.83 ERA. 841 career appearances."
        },
        {
            "name": "Alan Embree",
            "position": "RP",
            "years": "1992-2009",
            "peak_stats": "2.67 ERA (2003)",
            "fastball": 75, "curveball": 55, "slider": 65, "changeup": 50, "command": 60, "control": 60,
            "description": "Hard-throwing left-handed reliever. Power arm in middle innings with plus fastball.",
            "career_summary": "Career 4.08 ERA over 17 seasons. Durable lefty arm."
        },
        {
            "name": "Scott Williamson",
            "position": "RP",
            "years": "1999-2006",
            "peak_stats": "2.41 ERA, 19 SV (1999)",
            "fastball": 75, "curveball": 70, "slider": 65, "changeup": 55, "command": 60, "control": 60,
            "description": "Power reliever with plus stuff who could close or set up. Injuries limited career.",
            "career_summary": "ROY winner. 45 saves with 3.36 ERA. Career cut short by shoulder."
        },
        {
            "name": "Chad Bradford",
            "position": "RP",
            "years": "1998-2009",
            "peak_stats": "1.50 ERA (2002)",
            "fastball": 55, "curveball": 50, "slider": 60, "changeup": 55, "command": 80, "control": 80,
            "description": "Extreme submarine pitcher with elite ground ball rate. Deceptive delivery, low velocity.",
            "career_summary": "Career 3.21 ERA. Ground ball specialist with unique delivery."
        },
    ],

    # Elite setup relievers
    "setup_man": [
        {
            "name": "Mike Stanton",
            "position": "RP",
            "years": "1989-2007",
            "peak_stats": "2.29 ERA, 81 G (1998)",
            "fastball": 70, "curveball": 60, "slider": 70, "changeup": 55, "command": 70, "control": 70,
            "description": "Durable left-handed setup man with excellent slider. Iron-armed reliever who appeared everywhere.",
            "career_summary": "1,178 games (record at time). Career 3.92 ERA over 19 seasons."
        },
        {
            "name": "Jeff Nelson",
            "position": "RP",
            "years": "1992-2006",
            "peak_stats": "2.45 ERA (1996)",
            "fastball": 75, "curveball": 55, "slider": 80, "changeup": 50, "command": 65, "control": 60,
            "description": "Lanky right-hander with nasty slider from high three-quarters arm slot. Intimidating presence.",
            "career_summary": "Career 3.41 ERA. Key setup man for Yankees dynasty."
        },
        {
            "name": "Tom Gordon",
            "position": "RP",
            "years": "1988-2009",
            "peak_stats": "46 SV, 2.72 ERA (1998)",
            "fastball": 75, "curveball": 80, "slider": 65, "changeup": 55, "command": 65, "control": 65,
            "description": "Flash Gordon with devastating curveball. Transitioned from starter to elite reliever.",
            "career_summary": "Career 3.96 ERA with 158 saves. Plus curveball throughout career."
        },
        {
            "name": "Brendan Donnelly",
            "position": "RP",
            "years": "2002-2009",
            "peak_stats": "2.17 ERA (2003)",
            "fastball": 70, "curveball": 65, "slider": 70, "changeup": 55, "command": 70, "control": 70,
            "description": "Late bloomer who became a dominant setup man. Good slider and ability to strand runners.",
            "career_summary": "Career 3.23 ERA. Key part of Angels 2002 championship bullpen."
        },
        {
            "name": "Koji Uehara",
            "position": "RP",
            "years": "2009-2017",
            "peak_stats": "1.09 ERA, 21 SV (2013)",
            "fastball": 65, "curveball": 55, "slider": 55, "changeup": 50, "command": 85, "control": 85,
            "description": "Pinpoint command with deceptive splitter. Low velocity but unhittable at peak. Extreme control.",
            "career_summary": "Career 2.66 ERA in MLB. ALCS MVP 2013. Elite K/BB ratio."
        },
    ],

    # Crafty left-handers
    "crafty_lefty": [
        {
            "name": "Al Leiter",
            "position": "SP",
            "years": "1987-2005",
            "peak_stats": "17-6, 2.47 ERA (1998)",
            "fastball": 70, "curveball": 60, "slider": 65, "changeup": 65, "command": 70, "control": 65,
            "description": "Competitive lefty with good cutter and ability to pitch inside. Gutsy performer in big games.",
            "career_summary": "162 wins with 3.80 ERA. 2x All-Star. Big-game pitcher."
        },
        {
            "name": "Mark Buehrle",
            "position": "SP",
            "years": "2000-2015",
            "peak_stats": "16-8, 3.12 ERA (2005)",
            "fastball": 60, "curveball": 55, "slider": 55, "changeup": 70, "command": 80, "control": 80,
            "description": "Quick worker who pounded the zone. Relied on movement, deception, and elite fielding. Low velocity.",
            "career_summary": "214 wins with 3.81 ERA. Perfect game, no-hitter. 4x Gold Glove."
        },
        {
            "name": "Andy Pettitte",
            "position": "SP",
            "years": "1995-2013",
            "peak_stats": "21-8, 4.02 ERA (1996)",
            "fastball": 70, "curveball": 65, "slider": 60, "changeup": 60, "command": 75, "control": 75,
            "description": "Cutter-reliant lefty with excellent postseason pedigree. Durable and consistent competitor.",
            "career_summary": "256 wins with 3.85 ERA. All-time postseason wins leader (19)."
        },
        {
            "name": "Kenny Rogers",
            "position": "SP",
            "years": "1989-2008",
            "peak_stats": "18-4, 3.38 ERA (2004)",
            "fastball": 65, "curveball": 65, "slider": 60, "changeup": 70, "command": 75, "control": 75,
            "description": "Crafty lefty who reinvented himself multiple times. Perfect game in 1994. Late-career resurgence.",
            "career_summary": "219 wins with 4.27 ERA. Perfect game. Durable 20-year career."
        },
        {
            "name": "John Tudor",
            "position": "SP",
            "years": "1979-1990",
            "peak_stats": "21-8, 1.93 ERA (1985)",
            "fastball": 60, "curveball": 75, "slider": 55, "changeup": 70, "command": 80, "control": 80,
            "description": "Master of changing speeds and location. Dominated with below-average velocity through guile.",
            "career_summary": "117 wins with 3.12 ERA. Elite 1985 season. Crafty performer."
        },
    ],

    # Hard-throwing left-handed starters
    "power_lefty": [
        {
            "name": "Johan Santana",
            "position": "SP",
            "years": "2000-2012",
            "peak_stats": "19-6, 2.61 ERA (2004)",
            "fastball": 80, "curveball": 60, "slider": 70, "changeup": 80, "command": 80, "control": 75,
            "description": "Devastating changeup paired with mid-90s fastball. Best left-hander of his era at peak.",
            "career_summary": "139 wins with 3.20 ERA. 2x Cy Young. No-hitter with Mets."
        },
        {
            "name": "CC Sabathia",
            "position": "SP",
            "years": "2001-2019",
            "peak_stats": "19-7, 3.21 ERA (2007)",
            "fastball": 75, "curveball": 65, "slider": 75, "changeup": 65, "command": 70, "control": 70,
            "description": "Big, durable workhorse lefty with heavy fastball and power slider. Physical pitcher who evolved with age.",
            "career_summary": "251 wins with 3.74 ERA. Cy Young winner. 3,093 strikeouts."
        },
        {
            "name": "David Price",
            "position": "SP",
            "years": "2008-2022",
            "peak_stats": "20-5, 2.56 ERA (2012)",
            "fastball": 75, "curveball": 65, "slider": 60, "changeup": 70, "command": 75, "control": 75,
            "description": "Electric left-handed arm with plus velocity and command. Smooth delivery, maintained stuff deep into games.",
            "career_summary": "157 wins with 3.31 ERA. Cy Young winner. World Series champion."
        },
        {
            "name": "Clayton Kershaw",
            "position": "SP",
            "years": "2008-present",
            "peak_stats": "21-3, 1.77 ERA (2014)",
            "fastball": 75, "curveball": 80, "slider": 75, "changeup": 60, "command": 85, "control": 80,
            "description": "Generational lefty with devastating curveball and pinpoint command. Dominated the 2010s.",
            "career_summary": "200+ wins with 2.48 ERA. 3x Cy Young, MVP. Best ERA of modern era."
        },
        {
            "name": "Steve Carlton (late career)",
            "position": "SP",
            "years": "1965-1988",
            "peak_stats": "27-10, 1.97 ERA (1972)",
            "fastball": 70, "curveball": 65, "slider": 80, "changeup": 60, "command": 70, "control": 65,
            "description": "Lefty with legendary slider in his later years. Declining velocity but still plus-plus breaking ball.",
            "career_summary": "329 wins with 3.22 ERA. 4x Cy Young, Hall of Famer."
        },
    ],

    # Sinker/groundball specialists (starters)
    "sinker_specialist": [
        {
            "name": "Tim Hudson",
            "position": "SP",
            "years": "1999-2015",
            "peak_stats": "20-6, 2.98 ERA (2000)",
            "fastball": 70, "curveball": 60, "slider": 65, "changeup": 65, "command": 75, "control": 75,
            "description": "Elite sinker with heavy arm-side run. Generated extreme ground ball rates. Durable competitor.",
            "career_summary": "222 wins with 3.49 ERA. 4x All-Star. Consistently elite ground ball rate."
        },
        {
            "name": "Roy Halladay",
            "position": "SP",
            "years": "1998-2013",
            "peak_stats": "22-7, 2.44 ERA (2010)",
            "fastball": 75, "curveball": 75, "slider": 65, "changeup": 65, "command": 85, "control": 85,
            "description": "Power sinker with plus curveball and elite command. Complete package. Postseason no-hitter.",
            "career_summary": "203 wins with 3.38 ERA. 2x Cy Young, Hall of Famer."
        },
        {
            "name": "Chien-Ming Wang",
            "position": "SP",
            "years": "2005-2016",
            "peak_stats": "19-7, 3.63 ERA (2006)",
            "fastball": 75, "curveball": 50, "slider": 60, "changeup": 55, "command": 70, "control": 70,
            "description": "Extreme sinker-ball pitcher who generated ground balls at historic rate. One-pitch dominance.",
            "career_summary": "54 wins with 4.11 ERA. Dominant two-year peak before injury."
        },
        {
            "name": "Dallas Keuchel",
            "position": "SP",
            "years": "2012-2022",
            "peak_stats": "20-8, 2.48 ERA (2015)",
            "fastball": 65, "curveball": 55, "slider": 65, "changeup": 60, "command": 80, "control": 80,
            "description": "Soft-tossing sinker-baller with elite command. Induced weak contact and ground balls consistently.",
            "career_summary": "104 wins with 3.98 ERA. Cy Young winner. AL-leading ground ball rate."
        },
        {
            "name": "Rick Reuschel",
            "position": "SP",
            "years": "1972-1991",
            "peak_stats": "19-12, 2.79 ERA (1977)",
            "fastball": 65, "curveball": 65, "slider": 65, "changeup": 65, "command": 75, "control": 75,
            "description": "Underrated sinker-ball pitcher with excellent command. Durable and consistent over long career.",
            "career_summary": "214 wins with 3.37 ERA. 2x All-Star. Consistent ground ball producer."
        },
    ],

    # Flamethrowers (100mph+ relievers)
    "flamethrower": [
        {
            "name": "Aroldis Chapman",
            "position": "RP",
            "years": "2010-present",
            "peak_stats": "1.63 ERA, 38 SV (2012)",
            "fastball": 85, "curveball": 55, "slider": 70, "changeup": 40, "command": 55, "control": 55,
            "description": "Hardest-throwing pitcher in MLB history. 105.1 mph record. Pure velocity dominance.",
            "career_summary": "300+ saves with sub-2.00 ERA at peak. 7x All-Star."
        },
        {
            "name": "Joel Zumaya",
            "position": "RP",
            "years": "2006-2010",
            "peak_stats": "1.94 ERA (2006)",
            "fastball": 85, "curveball": 55, "slider": 70, "changeup": 45, "command": 50, "control": 50,
            "description": "Triple-digit heat with devastating slider. Electric arm destroyed by injuries. Raw power.",
            "career_summary": "Career 3.05 ERA. Threw 104 mph as rookie. Injuries ended promising career."
        },
        {
            "name": "Bobby Jenks",
            "position": "RP",
            "years": "2005-2011",
            "peak_stats": "41 SV, 2.75 ERA (2006)",
            "fastball": 80, "curveball": 65, "slider": 65, "changeup": 50, "command": 60, "control": 60,
            "description": "Big, physical power arm who threw upper-90s with curveball. World Series closer in 2005.",
            "career_summary": "173 saves with 3.56 ERA. Key to White Sox championship."
        },
        {
            "name": "Armando Benitez",
            "position": "RP",
            "years": "1994-2007",
            "peak_stats": "36 SV, 2.70 ERA (2004)",
            "fastball": 80, "curveball": 55, "slider": 70, "changeup": 50, "command": 55, "control": 55,
            "description": "Intimidating power arm with upper-90s heat and hard slider. Dominant stuff but blowup-prone.",
            "career_summary": "289 saves with 3.13 ERA. Elite stuff, inconsistent results."
        },
        {
            "name": "Rob Dibble",
            "position": "RP",
            "years": "1988-1995",
            "peak_stats": "1.74 ERA, 31 SV (1990)",
            "fastball": 80, "curveball": 55, "slider": 65, "changeup": 45, "command": 55, "control": 50,
            "description": "Nasty Boys member with 100mph heat. Volatile, aggressive pitcher with elite fastball.",
            "career_summary": "Career 2.98 ERA. Key to Reds 1990 championship. Short but intense career."
        },
    ],

    # Knuckleballers
    "knuckleballer": [
        {
            "name": "Tim Wakefield",
            "position": "SP",
            "years": "1992-2011",
            "peak_stats": "17-8, 2.95 ERA (1995)",
            "fastball": 45, "curveball": 40, "slider": 35, "changeup": 40, "command": 60, "control": 60,
            "description": "Knuckleball artist who reinvented himself from position player. Remarkably durable with dancing knuckler.",
            "career_summary": "200 wins with 4.41 ERA. Most wins in Red Sox modern history."
        },
        {
            "name": "R.A. Dickey",
            "position": "SP",
            "years": "2001-2017",
            "peak_stats": "20-6, 2.73 ERA (2012)",
            "fastball": 45, "curveball": 35, "slider": 35, "changeup": 40, "command": 65, "control": 60,
            "description": "Knuckleball pitcher who won Cy Young after reinventing himself. Unique story of perseverance.",
            "career_summary": "120 wins with 4.04 ERA. Cy Young winner in 2012."
        },
        {
            "name": "Charlie Hough",
            "position": "SP/RP",
            "years": "1970-1994",
            "peak_stats": "18-16, 3.32 ERA (1987)",
            "fastball": 50, "curveball": 40, "slider": 40, "changeup": 45, "command": 60, "control": 55,
            "description": "Durable knuckleballer who pitched 25 seasons. Moved from bullpen to rotation successfully.",
            "career_summary": "216 wins with 3.75 ERA. Pitched until age 46."
        },
        {
            "name": "Phil Niekro (late career)",
            "position": "SP",
            "years": "1964-1987",
            "peak_stats": "21-20, 3.39 ERA (1979)",
            "fastball": 50, "curveball": 40, "slider": 35, "changeup": 45, "command": 55, "control": 55,
            "description": "Hall of Fame knuckleballer in his later years. Still effective with dancing knuckleball into his 40s.",
            "career_summary": "318 wins with 3.35 ERA. Hall of Famer. Pitched until age 48."
        },
        {
            "name": "Tom Candiotti",
            "position": "SP",
            "years": "1983-1999",
            "peak_stats": "16-12, 2.65 ERA (1991)",
            "fastball": 50, "curveball": 45, "slider": 40, "changeup": 45, "command": 65, "control": 60,
            "description": "Knuckleballer with better-than-average secondary pitches. More polished than typical knuckler.",
            "career_summary": "151 wins with 3.73 ERA. Reliable innings eater with knuckleball."
        },
    ],
}


def find_best_comp(player_ratings: dict, position: str, is_pitcher: bool,
                   count: int = 1) -> list[dict]:
    """
    Find the best MLB comp(s) for a player using Euclidean distance matching.

    Args:
        player_ratings: Dict with tool ratings (contact, power, etc.)
        position: Player's position
        is_pitcher: Whether this is a pitcher
        count: Number of comps to return (default 1-3)

    Returns:
        List of dicts with comp info, reasoning, and career summary
    """
    if is_pitcher:
        return _find_pitcher_comp(player_ratings, position, count)
    else:
        return _find_position_comp(player_ratings, position, count)


def _find_position_comp(player_ratings: dict, position: str, count: int = 1) -> list[dict]:
    """Find position player comps."""
    # Get player tool ratings
    contact = player_ratings.get("contact_rating", 50)
    power = player_ratings.get("power_rating", 50)
    speed = player_ratings.get("speed_rating", 50)
    fielding = player_ratings.get("fielding_rating", 50)
    arm = player_ratings.get("arm_rating", 50)

    player_vector = (contact, power, speed, fielding, arm)

    # Determine which archetype pool to search
    pool = []
    reasoning = ""

    # Match archetype based on tool profile
    if power >= 70 and contact >= 55:
        # Power hitter archetype - route by position
        if position in ("1B", "DH"):
            if contact >= 55 and power >= 70 and speed <= 35:
                pool = POSITION_COMPS.get("dh_specialist", [])
                reasoning = "DH-type power hitter profile"
            else:
                pool = POSITION_COMPS.get("power_corner", [])
                reasoning = "Power-dominant corner bat profile"
        elif position in ("LF", "RF"):
            pool = POSITION_COMPS.get("power_of", [])
            reasoning = "Power-hitting outfielder profile"
        elif position == "3B":
            pool = POSITION_COMPS.get("power_3b", [])
            reasoning = "Power third baseman profile"
        elif position == "2B":
            pool = POSITION_COMPS.get("power_2b", [])
            reasoning = "Power second baseman profile"
    elif contact >= 70 and speed >= 70:
        # Speed/contact archetype
        if speed >= 75 and power <= 40:
            pool = POSITION_COMPS.get("leadoff_specialist", [])
            reasoning = "Classic leadoff hitter profile"
        elif position in ("CF", "LF", "RF"):
            pool = POSITION_COMPS.get("contact_speedster", [])
            reasoning = "Contact-speed outfielder profile"
        else:
            pool = POSITION_COMPS.get("contact_speedster", [])
            reasoning = "Contact-speed player profile"
    elif speed >= 70 and fielding >= 70:
        # Five-tool type
        if position == "CF":
            pool = POSITION_COMPS.get("five_tool_cf", [])
            reasoning = "Five-tool center fielder profile"
        elif fielding >= 75 and position in ("CF", "LF", "RF"):
            pool = POSITION_COMPS.get("defensive_of", [])
            reasoning = "Defense-first outfielder profile"
        else:
            pool = POSITION_COMPS.get("contact_speedster", [])
            reasoning = "Speed-defense player profile"
    elif speed >= 70 and power <= 35:
        # Pure speed, low power - leadoff type
        pool = POSITION_COMPS.get("leadoff_specialist", [])
        reasoning = "Speed-first leadoff profile"
    elif power >= 70 and position == "SS":
        # Power shortstop
        pool = POSITION_COMPS.get("power_ss", [])
        reasoning = "Power-hitting shortstop profile"
    elif power >= 60 and position == "3B":
        # Power third baseman
        pool = POSITION_COMPS.get("power_3b", [])
        reasoning = "Power third baseman profile"
    elif power >= 60 and position == "2B":
        # Power second baseman
        pool = POSITION_COMPS.get("power_2b", [])
        reasoning = "Power second baseman profile"
    elif fielding >= 75 and position == "SS":
        # Slick-fielding shortstop
        pool = POSITION_COMPS.get("slick_ss", [])
        reasoning = "Defensive shortstop profile"
    elif fielding >= 75 and position in ("CF", "LF", "RF"):
        # Gold Glove outfielder
        pool = POSITION_COMPS.get("defensive_of", [])
        reasoning = "Gold Glove outfielder profile"
    elif contact >= 75 and power >= 70:
        # OBP machine
        pool = POSITION_COMPS.get("obp_machine", [])
        reasoning = "High-average power hitter profile"
    elif contact >= 75 and power <= 50:
        # Gap hitter / line-drive type
        pool = POSITION_COMPS.get("gap_hitter", [])
        reasoning = "Line-drive gap hitter profile"
    elif position == "C":
        # Catcher
        pool = POSITION_COMPS.get("complete_catcher", [])
        reasoning = "Catcher profile"
    elif position == "DH" and speed <= 35:
        # DH specialist
        pool = POSITION_COMPS.get("dh_specialist", [])
        reasoning = "Designated hitter profile"
    elif fielding >= 65 and position in ("CF", "LF", "RF"):
        # Athletic outfielder with good defense
        pool = POSITION_COMPS.get("athletic_of", [])
        reasoning = "Athletic outfielder profile"
    elif contact >= 60 and position in ("2B", "3B"):
        # Balanced infielder
        pool = POSITION_COMPS.get("balanced_infielder", [])
        reasoning = "Balanced infielder profile"
    elif speed >= 60 and position in ("CF", "LF", "RF"):
        # Speedy outfielder
        pool = POSITION_COMPS.get("contact_speedster", [])
        reasoning = "Speed-oriented outfielder profile"
    elif contact >= 70:
        # High-contact hitter
        pool = POSITION_COMPS.get("gap_hitter", [])
        reasoning = "High-contact hitter profile"
    elif contact + power < 90:
        # Low ceiling player
        pool = POSITION_COMPS.get("low_ceiling_backup", [])
        reasoning = "Reserve/utility profile"
    else:
        # Position-aware default
        if position in ("CF", "LF", "RF"):
            pool = POSITION_COMPS.get("athletic_of", [])
            reasoning = "Outfielder profile"
        elif position == "SS":
            if power >= 55:
                pool = POSITION_COMPS.get("power_ss", [])
                reasoning = "Shortstop with pop profile"
            else:
                pool = POSITION_COMPS.get("slick_ss", [])
                reasoning = "Shortstop profile"
        elif position == "3B":
            pool = POSITION_COMPS.get("power_3b", [])
            reasoning = "Third baseman profile"
        elif position == "2B":
            pool = POSITION_COMPS.get("balanced_infielder", [])
            reasoning = "Infielder profile"
        elif position in ("1B", "DH"):
            pool = POSITION_COMPS.get("power_corner", [])
            reasoning = "Corner bat profile"
        elif position == "C":
            pool = POSITION_COMPS.get("complete_catcher", [])
            reasoning = "Catcher profile"
        else:
            pool = POSITION_COMPS.get("utility_defense", [])
            reasoning = "Mixed profile"

    # If we still don't have a pool, use the largest available
    if not pool:
        for archetype_name, comps in POSITION_COMPS.items():
            if comps:
                pool = comps
                reasoning = f"{archetype_name} profile"
                break

    if not pool:
        return []

    # Calculate distances to each comp in pool
    distances = []
    for comp in pool:
        comp_vector = (comp["contact"], comp["power"], comp["run"], comp["field"], comp["arm"])
        distance = sum((p - c) ** 2 for p, c in zip(player_vector, comp_vector)) ** 0.5
        distances.append((distance, comp))

    # Sort by distance and return top N
    distances.sort(key=lambda x: x[0])
    result = []
    for i, (dist, comp) in enumerate(distances[:count]):
        result.append({
            "rank": i + 1,
            "name": comp["name"],
            "position": comp["position"],
            "years": comp["years"],
            "peak_stats": comp["peak_stats"],
            "tools": {
                "contact": comp["contact"],
                "power": comp["power"],
                "speed": comp["run"],
                "fielding": comp["field"],
                "arm": comp["arm"],
            },
            "description": comp["description"],
            "career_summary": comp["career_summary"],
            "reasoning": reasoning if i == 0 else "",
        })

    return result


def _find_pitcher_comp(player_ratings: dict, position: str, count: int = 1) -> list[dict]:
    """Find pitcher comps."""
    # Get pitcher tool ratings
    stuff_rating = player_ratings.get("stuff_rating", 50)
    control_rating = player_ratings.get("control_rating", 50)

    # Build a meaningful vector from stuff/control ratings:
    # - fastball: pure stuff
    # - curveball/slider: movement proxy derived from stuff
    # - changeup: blend of stuff and control
    # - command/control: pure control
    fastball = stuff_rating
    curveball = int(stuff_rating * 0.9)
    slider = int(stuff_rating * 0.85)
    changeup = int((stuff_rating + control_rating) / 2)
    command = control_rating
    control = control_rating

    player_vector = (fastball, curveball, slider, changeup, command, control)

    # Determine archetype
    pool = []
    reasoning = ""

    if position == "RP":
        # Reliever archetypes
        if fastball >= 80:
            pool = PITCHER_COMPS.get("flamethrower", [])
            reasoning = "Flamethrower profile"
        elif fastball >= 75 and control >= 75:
            pool = PITCHER_COMPS.get("power_closer", [])
            reasoning = "Power closer profile"
        elif fastball >= 70 and control >= 65:
            pool = PITCHER_COMPS.get("setup_man", [])
            reasoning = "Setup man profile"
        else:
            pool = PITCHER_COMPS.get("middle_reliever", [])
            reasoning = "Middle reliever profile"
    else:
        # Starter archetypes
        if fastball <= 50 and command <= 65:
            # Knuckleball profile (very low velocity, moderate control)
            pool = PITCHER_COMPS.get("knuckleballer", [])
            reasoning = "Knuckleballer profile"
        elif fastball >= 80 and curveball >= 75:
            pool = PITCHER_COMPS.get("ace_starter", [])
            reasoning = "Ace starter profile"
        elif fastball >= 75 and command >= 75:
            # Power lefty / power starter with command
            pool = PITCHER_COMPS.get("power_lefty", [])
            reasoning = "Power left-hander profile"
        elif command >= 85:
            pool = PITCHER_COMPS.get("finesse_starter", [])
            reasoning = "Finesse starter profile"
        elif command >= 75 and fastball <= 70:
            # Crafty lefty type (command over stuff)
            pool = PITCHER_COMPS.get("crafty_lefty", [])
            reasoning = "Crafty pitcher profile"
        elif (fastball + curveball + slider) / 3 >= 70:
            pool = PITCHER_COMPS.get("strikeout_artist", [])
            reasoning = "Strikeout artist profile"
        elif command >= 70 and slider >= 65:
            pool = PITCHER_COMPS.get("sinker_specialist", [])
            reasoning = "Sinker/groundball specialist profile"
        elif slider >= 70:
            pool = PITCHER_COMPS.get("ground_ball_sp", [])
            reasoning = "Ground ball specialist profile"
        else:
            pool = PITCHER_COMPS.get("innings_eater", [])
            reasoning = "Innings eater profile"

    if not pool:
        for archetype_name, comps in PITCHER_COMPS.items():
            if comps:
                pool = comps
                reasoning = f"{archetype_name} profile"
                break

    if not pool:
        return []

    # Calculate distances
    distances = []
    for comp in pool:
        comp_vector = (comp["fastball"], comp["curveball"], comp["slider"],
                       comp["changeup"], comp["command"], comp["control"])
        distance = sum((p - c) ** 2 for p, c in zip(player_vector, comp_vector)) ** 0.5
        distances.append((distance, comp))

    distances.sort(key=lambda x: x[0])
    result = []
    for i, (dist, comp) in enumerate(distances[:count]):
        result.append({
            "rank": i + 1,
            "name": comp["name"],
            "position": comp["position"],
            "years": comp["years"],
            "peak_stats": comp["peak_stats"],
            "tools": {
                "fastball": comp["fastball"],
                "curveball": comp["curveball"],
                "slider": comp["slider"],
                "changeup": comp["changeup"],
                "command": comp["command"],
                "control": comp["control"],
            },
            "description": comp["description"],
            "career_summary": comp["career_summary"],
            "reasoning": reasoning if i == 0 else "",
        })

    return result
