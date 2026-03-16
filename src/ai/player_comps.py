"""
Front Office - Player Comparisons Database
Comprehensive MLB comp database using 1985-2011 era players.
Organized by archetype with tool profiles and career details.
"""
import random
from typing import Optional


# Position player archetypes (1985-2011 era)
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
    ],
}


# Pitcher archetypes (1985-2011 era)
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
        # Power hitter archetype
        if position in ("1B", "DH"):
            pool = POSITION_COMPS.get("power_corner", [])
            reasoning = "Power-dominant corner bat profile"
        elif position in ("LF", "RF"):
            pool = POSITION_COMPS.get("power_corner", [])
            reasoning = "Power-hitting outfielder profile"
    elif contact >= 70 and speed >= 70:
        # Speed/contact archetype
        if position in ("CF", "LF", "RF"):
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
        else:
            pool = POSITION_COMPS.get("contact_speedster", [])
    elif power >= 70 and position == "SS":
        # Power shortstop
        pool = POSITION_COMPS.get("power_ss", [])
        reasoning = "Power-hitting shortstop profile"
    elif fielding >= 75 and position == "SS":
        # Slick-fielding shortstop
        pool = POSITION_COMPS.get("slick_ss", [])
        reasoning = "Defensive shortstop profile"
    elif contact >= 75 and power >= 70:
        # OBP machine
        pool = POSITION_COMPS.get("obp_machine", [])
        reasoning = "High-average power hitter profile"
    elif position == "C":
        # Catcher
        pool = POSITION_COMPS.get("complete_catcher", [])
        reasoning = "Catcher profile"
    elif contact + power < 90:
        # Low ceiling player
        pool = POSITION_COMPS.get("low_ceiling_backup", [])
        reasoning = "Reserve/utility profile"
    else:
        # Default to generic pool
        pool = POSITION_COMPS.get("power_corner", [])
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
    fastball = player_ratings.get("stuff_rating", 50)
    curveball = player_ratings.get("control_rating", 50)
    slider = player_ratings.get("control_rating", 50)
    changeup = player_ratings.get("control_rating", 50)
    command = player_ratings.get("control_rating", 50)
    control = player_ratings.get("control_rating", 50)

    player_vector = (fastball, curveball, slider, changeup, command, control)

    # Determine archetype
    pool = []
    reasoning = ""

    if position == "RP":
        # Reliever
        if fastball >= 75 and control >= 75:
            pool = PITCHER_COMPS.get("power_closer", [])
            reasoning = "Power closer profile"
        else:
            pool = PITCHER_COMPS.get("middle_reliever", [])
            reasoning = "Middle reliever profile"
    else:
        # Starter
        if fastball >= 80 and curveball >= 75:
            pool = PITCHER_COMPS.get("ace_starter", [])
            reasoning = "Ace starter profile"
        elif command >= 85:
            pool = PITCHER_COMPS.get("finesse_starter", [])
            reasoning = "Finesse starter profile"
        elif (fastball + curveball + slider) / 3 >= 70:
            pool = PITCHER_COMPS.get("strikeout_artist", [])
            reasoning = "Strikeout artist profile"
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
