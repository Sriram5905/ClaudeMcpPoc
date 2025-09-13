#!/usr/bin/env python3

import asyncio
import sys
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from bson import ObjectId

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server import NotificationOptions
    from mcp.types import Tool, TextContent
    import mcp.types as types
    print("MCP imports successful")
except ImportError as e:
    print(f"MCP import error: {e}")
    print("Please install MCP with: pip install mcp")
    sys.exit(1)

# MongoDB imports
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    print("MongoDB imports successful")
except ImportError as e:
    print(f"MongoDB import error: {e}")
    print("Please install pymongo with: pip install pymongo")
    sys.exit(1)

# Initialize MCP server
server = Server("resume-analyzer")

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "resumes_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "candidates")

# MongoDB client
mongo_client = None

def get_database():
    """Get MongoDB database connection"""
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return mongo_client[DATABASE_NAME]

def format_resume_display(resume: Dict) -> str:
    """Format resume data for display"""
    if not resume:
        return "Resume not found"
    
    result = f"**{resume.get('name', 'Unknown')}**\n"
    result += f"Email: {resume.get('email', 'N/A')}\n"
    result += f"Phone: {resume.get('phone', 'N/A')}\n"
    result += f"ID: {resume.get('_id', 'N/A')}\n\n"
    
    # Skills section
    skills = resume.get('skills', [])
    if skills:
        result += f"**Skills** ({len(skills)}):\n"
        for i, skill in enumerate(skills, 1):
            result += f"   {i}. {skill}\n"
        result += "\n"
    
    # Experience section
    experience = resume.get('experience', [])
    if experience:
        result += f"**Experience** ({len(experience)} positions):\n"
        for i, exp in enumerate(experience, 1):
            if isinstance(exp, dict):
                title = exp.get('title', 'Unknown Position')
                company = exp.get('company', 'Unknown Company')
                duration = exp.get('duration', 'Unknown Duration')
                result += f"   {i}. {title} at {company} ({duration})\n"
            else:
                result += f"   {i}. {exp}\n"
        result += "\n"
    
    # Education section
    education = resume.get('education', [])
    if education:
        result += f"**Education** ({len(education)}):\n"
        for i, edu in enumerate(education, 1):
            if isinstance(edu, dict):
                degree = edu.get('degree', 'Unknown Degree')
                school = edu.get('school', 'Unknown School')
                year = edu.get('year', 'Unknown Year')
                result += f"   {i}. {degree} from {school} ({year})\n"
            else:
                result += f"   {i}. {edu}\n"
        result += "\n"
    
    # Summary section
    summary = resume.get('summary', '')
    if summary:
        result += f"**Summary**:\n{summary[:200]}{'...' if len(summary) > 200 else ''}\n"
    
    return result

def analyze_experience_level(experience: List) -> str:
    """Analyze experience level based on number of positions"""
    if not experience:
        return "entry"
    elif len(experience) <= 2:
        return "entry"
    elif len(experience) <= 5:
        return "mid"
    else:
        return "senior"

def calculate_resume_score(resume: Dict, job_requirements: List[str] = None) -> Dict:
    """Calculate comprehensive resume score"""
    score = 0
    max_score = 100
    details = []
    
    # Skills scoring (30 points)
    skills = resume.get('skills', [])
    skills_score = min(len(skills) * 3, 30)
    score += skills_score
    details.append(f"Skills: {skills_score}/30 ({len(skills)} skills)")
    
    # Experience scoring (35 points)
    experience = resume.get('experience', [])
    exp_score = min(len(experience) * 7, 35)
    score += exp_score
    details.append(f"Experience: {exp_score}/35 ({len(experience)} positions)")
    
    # Education scoring (20 points)
    education = resume.get('education', [])
    edu_score = min(len(education) * 10, 20)
    score += edu_score
    details.append(f"Education: {edu_score}/20 ({len(education)} qualifications)")
    
    # Contact info scoring (10 points)
    contact_score = 0
    if resume.get('email'): contact_score += 5
    if resume.get('phone'): contact_score += 5
    score += contact_score
    details.append(f"Contact Info: {contact_score}/10")
    
    # Summary scoring (5 points)
    summary = resume.get('summary', '')
    summary_score = 5 if summary and len(summary) > 50 else 0
    score += summary_score
    details.append(f"Summary: {summary_score}/5")
    
    # Job requirements matching bonus
    if job_requirements:
        matching_skills = 0
        for req in job_requirements:
            for skill in skills:
                if req.lower() in skill.lower():
                    matching_skills += 1
                    break
        req_score = (matching_skills / len(job_requirements)) * 20 if job_requirements else 0
        score += req_score
        max_score += 20
        details.append(f"Job Match: {req_score:.1f}/20 ({matching_skills}/{len(job_requirements)} requirements)")
    
    return {
        'score': score,
        'max_score': max_score,
        'percentage': (score / max_score) * 100,
        'details': details,
        'grade': 'A' if score >= max_score * 0.8 else 'B' if score >= max_score * 0.6 else 'C' if score >= max_score * 0.4 else 'D'
    }

@server.list_tools()
async def list_tools():
    """List available resume analysis tools"""
    return [
        Tool(
            name="get_all_resumes",
            description="Retrieve all resumes from the MongoDB database",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Limit number of results (default: 10)"}
                }
            }
        ),
        Tool(
            name="get_resume_by_id",
            description="Get a specific resume by MongoDB ObjectId",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_id": {"type": "string", "description": "MongoDB ObjectId of the resume"}
                },
                "required": ["resume_id"]
            }
        ),
        Tool(
            name="search_by_skill",
            description="Search resumes containing specific skills",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "description": "Skill to search for"},
                    "limit": {"type": "integer", "description": "Limit results (default: 5)"}
                },
                "required": ["skill"]
            }
        ),
        Tool(
            name="search_by_name",
            description="Search resumes by candidate name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name to search for"},
                    "exact": {"type": "boolean", "description": "Exact match (default: false)"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="analyze_skills_distribution",
            description="Analyze skills distribution across all resumes",
            inputSchema={
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "Number of top skills to show (default: 10)"}
                }
            }
        ),
        Tool(
            name="get_experience_analysis",
            description="Analyze experience levels across resumes",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="calculate_resume_score",
            description="Calculate comprehensive score for a resume",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_id": {"type": "string", "description": "Resume ObjectId"},
                    "job_requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional job requirements to match against"
                    }
                },
                "required": ["resume_id"]
            }
        ),
        Tool(
            name="compare_resumes",
            description="Compare two resumes side by side",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_id1": {"type": "string", "description": "First resume ObjectId"},
                    "resume_id2": {"type": "string", "description": "Second resume ObjectId"}
                },
                "required": ["resume_id1", "resume_id2"]
            }
        ),
        Tool(
            name="find_similar_resumes",
            description="Find resumes similar to a given resume based on skills",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_id": {"type": "string", "description": "Reference resume ObjectId"},
                    "limit": {"type": "integer", "description": "Number of similar resumes to return (default: 3)"}
                },
                "required": ["resume_id"]
            }
        ),
        Tool(
            name="get_database_stats",
            description="Get statistics about the resume database",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict,context: Optional[dict] = None):    
    # You can log or use the context if needed
    
    
    try:
        db = get_database()
        collection = db[COLLECTION_NAME]
        
        if name == "get_all_resumes":
            limit = arguments.get("limit", 10)
            resumes = list(collection.find({}).limit(limit))
            
            if not resumes:
                return [TextContent(type="text", text="No resumes found in the database.")]
            
            result = f"**Found {len(resumes)} resumes:**\n\n"
            for i, resume in enumerate(resumes, 1):
                result += f"**{i}. {resume.get('name', 'Unknown')}**\n"
                result += f"   Email: {resume.get('email', 'N/A')}\n"
                result += f"   Skills: {len(resume.get('skills', []))}\n"
                result += f"   Experience: {len(resume.get('experience', []))}\n"
                result += f"   ID: {resume.get('_id')}\n\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_resume_by_id":
            resume_id = arguments["resume_id"]
            try:
                object_id = ObjectId(resume_id)
                resume = collection.find_one({"_id": object_id})
                
                if not resume:
                    return [TextContent(type="text", text=f"Resume with ID {resume_id} not found.")]
                
                result = format_resume_display(resume)
                return [TextContent(type="text", text=result)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"Invalid ObjectId format: {resume_id}")]
        
        elif name == "search_by_skill":
            skill = arguments["skill"]
            limit = arguments.get("limit", 5)
            
            # Case-insensitive search for skill
            regex_pattern = re.compile(skill, re.IGNORECASE)
            resumes = list(collection.find({"skills": {"$regex": regex_pattern}}).limit(limit))
            
            if not resumes:
                return [TextContent(type="text", text=f"No resumes found with skill: {skill}")]
            
            result = f"**Found {len(resumes)} resumes with skill '{skill}':**\n\n"
            for i, resume in enumerate(resumes, 1):
                matching_skills = [s for s in resume.get('skills', []) if skill.lower() in s.lower()]
                result += f"**{i}. {resume.get('name', 'Unknown')}**\n"
                result += f"   Email: {resume.get('email', 'N/A')}\n"
                result += f"   Matching skills: {', '.join(matching_skills)}\n"
                result += f"   ID: {resume.get('_id')}\n\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "search_by_name":
            name = arguments["name"]
            exact = arguments.get("exact", False)
            
            if exact:
                query = {"name": name}
            else:
                query = {"name": {"$regex": re.compile(name, re.IGNORECASE)}}
            
            resumes = list(collection.find(query))
            
            if not resumes:
                return [TextContent(type="text", text=f"No resumes found for name: {name}")]
            
            result = f"**Found {len(resumes)} resume(s) for '{name}':**\n\n"
            for resume in resumes:
                result += format_resume_display(resume) + "\n" + "="*50 + "\n\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "analyze_skills_distribution":
            top_n = arguments.get("top_n", 10)
            
            # Aggregate skills across all resumes
            pipeline = [
                {"$unwind": "$skills"},
                {"$group": {"_id": "$skills", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": top_n}
            ]
            
            skills_data = list(collection.aggregate(pipeline))
            
            if not skills_data:
                return [TextContent(type="text", text="No skills data found.")]
            
            total_resumes = collection.count_documents({})
            result = f"**Top {len(skills_data)} Skills Distribution** (from {total_resumes} resumes):\n\n"
            
            for i, skill_info in enumerate(skills_data, 1):
                skill = skill_info['_id']
                count = skill_info['count']
                percentage = (count / total_resumes) * 100
                result += f"{i:2d}. **{skill}**: {count} resumes ({percentage:.1f}%)\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_experience_analysis":
            resumes = list(collection.find({}))
            
            if not resumes:
                return [TextContent(type="text", text="No resumes found for analysis.")]
            
            experience_levels = {"entry": 0, "mid": 0, "senior": 0}
            experience_details = []
            
            for resume in resumes:
                level = analyze_experience_level(resume.get('experience', []))
                experience_levels[level] += 1
                experience_details.append({
                    'name': resume.get('name', 'Unknown'),
                    'level': level,
                    'experience_count': len(resume.get('experience', []))
                })
            
            total = len(resumes)
            result = f"**Experience Level Analysis** ({total} resumes):\n\n"
            result += f"**Entry Level**: {experience_levels['entry']} ({experience_levels['entry']/total*100:.1f}%)\n"
            result += f"**Mid Level**: {experience_levels['mid']} ({experience_levels['mid']/total*100:.1f}%)\n"
            result += f"**Senior Level**: {experience_levels['senior']} ({experience_levels['senior']/total*100:.1f}%)\n\n"
            
            result += "**Detailed Breakdown:**\n"
            for detail in sorted(experience_details, key=lambda x: x['experience_count'], reverse=True):
                result += f"• {detail['name']}: {detail['level'].title()} ({detail['experience_count']} positions)\n"
            
            return [TextContent(type="text", text=result)]
        
        elif name == "calculate_resume_score":
            resume_id = arguments["resume_id"]
            job_requirements = arguments.get("job_requirements", [])
            
            try:
                object_id = ObjectId(resume_id)
                resume = collection.find_one({"_id": object_id})
                
                if not resume:
                    return [TextContent(type="text", text=f"Resume with ID {resume_id} not found.")]
                
                score_data = calculate_resume_score(resume, job_requirements)
                
                result = f"**Resume Score for {resume.get('name', 'Unknown')}**\n\n"
                result += f"**Overall Score**: {score_data['score']:.1f}/{score_data['max_score']} ({score_data['percentage']:.1f}%)\n"
                result += f"**Grade**: {score_data['grade']}\n\n"
                result += "**Score Breakdown:**\n"
                for detail in score_data['details']:
                    result += f"• {detail}\n"
                
                if job_requirements:
                    result += f"\n**Job Requirements Analyzed**: {', '.join(job_requirements)}"
                
                return [TextContent(type="text", text=result)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"Error processing resume: {str(e)}")]
        
        elif name == "compare_resumes":
            resume_id1 = arguments["resume_id1"]
            resume_id2 = arguments["resume_id2"]
            
            try:
                object_id1 = ObjectId(resume_id1)
                object_id2 = ObjectId(resume_id2)
                
                resume1 = collection.find_one({"_id": object_id1})
                resume2 = collection.find_one({"_id": object_id2})
                
                if not resume1:
                    return [TextContent(type="text", text=f"Resume 1 with ID {resume_id1} not found.")]
                if not resume2:
                    return [TextContent(type="text", text=f"Resume 2 with ID {resume_id2} not found.")]
                
                # Calculate scores for both
                score1 = calculate_resume_score(resume1)
                score2 = calculate_resume_score(resume2)
                
                result = f"**Resume Comparison**\n\n"
                result += f"**Candidate 1: {resume1.get('name', 'Unknown')}**\n"
                result += f"Score: {score1['score']:.1f}/{score1['max_score']} ({score1['percentage']:.1f}%) - Grade {score1['grade']}\n"
                result += f"Skills: {len(resume1.get('skills', []))}\n"
                result += f"Experience: {len(resume1.get('experience', []))}\n"
                result += f"Education: {len(resume1.get('education', []))}\n\n"
                
                result += f"**Candidate 2: {resume2.get('name', 'Unknown')}**\n"
                result += f"Score: {score2['score']:.1f}/{score2['max_score']} ({score2['percentage']:.1f}%) - Grade {score2['grade']}\n"
                result += f"Skills: {len(resume2.get('skills', []))}\n"
                result += f"Experience: {len(resume2.get('experience', []))}\n"
                result += f"Education: {len(resume2.get('education', []))}\n\n"
                
                # Determine winner
                if score1['percentage'] > score2['percentage']:
                    result += f"**Winner**: {resume1.get('name', 'Candidate 1')} (by {score1['percentage'] - score2['percentage']:.1f}%)"
                elif score2['percentage'] > score1['percentage']:
                    result += f"**Winner**: {resume2.get('name', 'Candidate 2')} (by {score2['percentage'] - score1['percentage']:.1f}%)"
                else:
                    result += "**Result**: Tie!"
                
                # Common skills
                skills1 = set(resume1.get('skills', []))
                skills2 = set(resume2.get('skills', []))
                common_skills = skills1.intersection(skills2)
                
                if common_skills:
                    result += f"\n\n**Common Skills**: {', '.join(common_skills)}"
                
                return [TextContent(type="text", text=result)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"Error comparing resumes: {str(e)}")]
        
        elif name == "find_similar_resumes":
            resume_id = arguments["resume_id"]
            limit = arguments.get("limit", 3)
            
            try:
                object_id = ObjectId(resume_id)
                reference_resume = collection.find_one({"_id": object_id})
                
                if not reference_resume:
                    return [TextContent(type="text", text=f"Reference resume with ID {resume_id} not found.")]
                
                reference_skills = set(reference_resume.get('skills', []))
                
                if not reference_skills:
                    return [TextContent(type="text", text="Reference resume has no skills to compare against.")]
                
                # Find resumes with overlapping skills
                all_resumes = list(collection.find({"_id": {"$ne": object_id}}))
                similarities = []
                
                for resume in all_resumes:
                    resume_skills = set(resume.get('skills', []))
                    if resume_skills:
                        common_skills = reference_skills.intersection(resume_skills)
                        similarity_score = len(common_skills) / len(reference_skills.union(resume_skills))
                        
                        if similarity_score > 0:
                            similarities.append({
                                'resume': resume,
                                'score': similarity_score,
                                'common_skills': common_skills
                            })
                
                # Sort by similarity score
                similarities.sort(key=lambda x: x['score'], reverse=True)
                similarities = similarities[:limit]
                
                if not similarities:
                    return [TextContent(type="text", text="No similar resumes found.")]
                
                result = f"**Similar Resumes to {reference_resume.get('name', 'Unknown')}**\n\n"
                result += f"**Reference Skills**: {', '.join(reference_skills)}\n\n"
                
                for i, sim in enumerate(similarities, 1):
                    resume = sim['resume']
                    score = sim['score']
                    common = sim['common_skills']
                    
                    result += f"**{i}. {resume.get('name', 'Unknown')}** (Similarity: {score:.1%})\n"
                    result += f"   Email: {resume.get('email', 'N/A')}\n"
                    result += f"   Common Skills: {', '.join(common)}\n"
                    result += f"   ID: {resume.get('_id')}\n\n"
                
                return [TextContent(type="text", text=result)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"Error finding similar resumes: {str(e)}")]
        
        elif name == "get_database_stats":
            total_resumes = collection.count_documents({})
            
            if total_resumes == 0:
                return [TextContent(type="text", text="Database is empty.")]
            
            # Get various statistics
            stats = {
                'total_resumes': total_resumes,
                'resumes_with_skills': collection.count_documents({"skills": {"$exists": True, "$ne": []}}),
                'resumes_with_experience': collection.count_documents({"experience": {"$exists": True, "$ne": []}}),
                'resumes_with_education': collection.count_documents({"education": {"$exists": True, "$ne": []}}),
                'resumes_with_email': collection.count_documents({"email": {"$exists": True, "$ne": ""}}),
                'resumes_with_phone': collection.count_documents({"phone": {"$exists": True, "$ne": ""}}),
            }
            
            # Calculate averages
            pipeline = [
                {"$project": {
                    "skills_count": {"$size": {"$ifNull": ["$skills", []]}},
                    "experience_count": {"$size": {"$ifNull": ["$experience", []]}},
                    "education_count": {"$size": {"$ifNull": ["$education", []]}}
                }},
                {"$group": {
                    "_id": None,
                    "avg_skills": {"$avg": "$skills_count"},
                    "avg_experience": {"$avg": "$experience_count"},
                    "avg_education": {"$avg": "$education_count"}
                }}
            ]
            
            avg_data = list(collection.aggregate(pipeline))
            averages = avg_data[0] if avg_data else {}
            
            result = f"**Resume Database Statistics**\n\n"
            result += f"**Total Resumes**: {stats['total_resumes']}\n\n"
            
            result += f"**Data Completeness:**\n"
            result += f"• Resumes with Skills: {stats['resumes_with_skills']} ({stats['resumes_with_skills']/total_resumes*100:.1f}%)\n"
            result += f"• Resumes with Experience: {stats['resumes_with_experience']} ({stats['resumes_with_experience']/total_resumes*100:.1f}%)\n"
            result += f"• Resumes with Education: {stats['resumes_with_education']} ({stats['resumes_with_education']/total_resumes*100:.1f}%)\n"
            result += f"• Resumes with Email: {stats['resumes_with_email']} ({stats['resumes_with_email']/total_resumes*100:.1f}%)\n"
            result += f"• Resumes with Phone: {stats['resumes_with_phone']} ({stats['resumes_with_phone']/total_resumes*100:.1f}%)\n\n"
            
            if averages:
                result += f"**Averages per Resume:**\n"
                result += f"• Skills: {averages.get('avg_skills', 0):.1f}\n"
                result += f"• Experience Positions: {averages.get('avg_experience', 0):.1f}\n"
                result += f"• Education Entries: {averages.get('avg_education', 0):.1f}\n"
            
            return [TextContent(type="text", text=result)]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except ConnectionFailure:
        return [TextContent(type="text", text="Failed to connect to MongoDB. Please check your connection.")]
    except ServerSelectionTimeoutError:
        return [TextContent(type="text", text="MongoDB server selection timeout. Please check if MongoDB is running.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Main function to run the MCP server"""
    try:
        # Test MongoDB connection
        db = get_database()
        mongo_client = MongoClient(MONGODB_URI)
        admin_db = mongo_client["admin"]
        admin_db.command("ping")
        print(f"Connected to MongoDB: {DATABASE_NAME}.{COLLECTION_NAME}")
        
        from mcp.server.stdio import stdio_server
        print("Starting Resume Analyzer MCP server...")
        
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="resume-analyzer",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except Exception as e:
        print(f"Server error: {e}")
        raise

if __name__ == "__main__":
    print("Testing imports and connections...")
    asyncio.run(main())