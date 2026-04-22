from fastapi import FastAPI, Request, Form, File, UploadFile, Depends, HTTPException, status, Body
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import firestore
import requests
import uuid
import uvicorn

# App setup
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Firebase setup
FIREBASE_WEB_API_KEY = "AIzaSyDCB3O_hIKmXrEtVViEdl69a95hdq7ZcfM"
SERVICE_ACCOUNT_FILE = "firebase-credentials.json"
PROJECT_ID = "assignment-3-d2d70"

# Firestore client
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
db = firestore.Client(credentials=credentials, project=PROJECT_ID)

# Get OAuth token for Firestore REST API access
def get_service_token():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/datastore"]
    )
    creds.refresh(GoogleAuthRequest())
    return creds.token

# Helper function to validate Firebase ID token and return user info
def get_current_user(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    user_info = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
        json={"idToken": token}
    ).json()

    if "users" not in user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return user_info["users"][0]

# Pydantic model for signup form
class SignupData(BaseModel):
    fullname: str

# Homepage timeline
@app.get("/", response_class=HTMLResponse)
async def timeline(request: Request):
    try:
        user = get_current_user(request)
        current_email = user["email"]

        user_doc = db.collection("User").document(current_email).get()
        following_list = []

        if user_doc.exists:
            raw_following = user_doc.to_dict().get("Following", [])
            for item in raw_following:
                if isinstance(item, dict):
                    following_list.append(item.get("email"))
                elif isinstance(item, str):
                    following_list.append(item)

        users_to_fetch = following_list + [current_email]

        query_url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents:runQuery"
        query_payload = {
            "structuredQuery": {
                "from": [{"collectionId": "Post"}],
                "where": {
                    "compositeFilter": {
                        "op": "OR",
                        "filters": [
                            {"fieldFilter": {
                                "field": {"fieldPath": "Username"},
                                "op": "EQUAL",
                                "value": {"stringValue": email}
                            }} for email in users_to_fetch
                        ]
                    }
                },
                "orderBy": [{
                    "field": {"fieldPath": "Date"},
                    "direction": "DESCENDING"
                }],
                "limit": 50
            }
        }

        headers = {"Authorization": f"Bearer {get_service_token()}"}
        result = requests.post(query_url, json=query_payload, headers=headers)

        posts = []
        if result.status_code == 200:
            for doc in result.json():
                if "document" in doc:
                    fields = doc["document"]["fields"]
                    posts.append(fields)

            return templates.TemplateResponse("main.html", {
                "request": request,
                "posts": posts
            })
        else:
            return HTMLResponse("<h3 style='color:white;'>Failed to load timeline</h3>", status_code=500)

    except Exception:
        return RedirectResponse("/login", status_code=302)

# Login page
@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Signup form page
@app.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("sign_up.html", {"request": request})

# Signup data processing
@app.post("/signup")
async def signup_post(data: SignupData = Body(...), request: Request = None, user=Depends(get_current_user)):
    profile_name = data.fullname

    user_doc_ref = db.collection("User").document(user["email"])
    user_doc_ref.set({
        "email": user["email"],
        "ProfileName": profile_name,
        "Followers": [],
        "Following": []
    })

    return {"message": "Signup successful"}


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("search.html", {"request": request})

@app.get("/search_user")
async def search_user(request: Request, query: str):
    token = request.cookies.get("token")
    if not token:
        return []

    user_info = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
        json={"idToken": token}
    ).json()

    if "users" not in user_info:
        return []

    current_email = user_info["users"][0]["email"]

    credentials = service_account.Credentials.from_service_account_file(
        "firebase-credentials.json"
    )
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    users = db.collection("User").stream()

    matching_users = []
    for user in users:
        data = user.to_dict()
        profile_name = data.get("ProfileName", "")
        email = user.id

        if profile_name.lower().startswith(query.lower()) and email != current_email:
            matching_users.append({
                "profile_name": profile_name,
                "email": email
            })

    return matching_users

@app.post("/init_user")
async def init_user(request: Request):
    token = request.cookies.get("token")
    if not token:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    user_info = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
        json={"idToken": token}
    ).json()

    if "users" not in user_info:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    email = user_info["users"][0]["email"]
    credentials = service_account.Credentials.from_service_account_file(
        "firebase-credentials.json"
    )
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    user_ref = db.collection("User").document(email)
    user_doc = user_ref.get()

    if not user_doc.exists:
        user_ref.set({
            "Followers": [],
            "Following": [],
            "ProfileName": email.split("@")[0]
        })

    return {"status": "User Initialized"}

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    try:
        user_info = requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
            json={"idToken": token}
        ).json()

        if "users" not in user_info:
            return RedirectResponse("/login", status_code=302)

        email = user_info["users"][0]["email"]
    except Exception:
        return RedirectResponse("/login", status_code=302)

    credentials = service_account.Credentials.from_service_account_file(
        "firebase-credentials.json"
    )
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")
    user_doc = db.collection("User").document(email).get()
    followers_count = 0
    following_count = 0
    if user_doc.exists:
        user_data = user_doc.to_dict()
        followers_count = len(user_data.get("Followers", []))
        following_count = len(user_data.get("Following", []))

    project_id = "assignment-3-d2d70"
    query_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents:runQuery"
    query_payload = {
        "structuredQuery": {
            "from": [{"collectionId": "Post"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "Username"},
                    "op": "EQUAL",
                    "value": {"stringValue": email}
                }
            },
            "orderBy": [{
                "field": {"fieldPath": "Date"},
                "direction": "DESCENDING"
            }]
        }
    }

    headers = {"Authorization": f"Bearer {get_service_token()}"}
    result = requests.post(query_url, json=query_payload, headers=headers)

    if result.status_code == 200:
        posts = []
        for doc in result.json():
            if "document" in doc:
                fields = doc["document"]["fields"]
                posts.append(fields)

        return templates.TemplateResponse("profile.html", {
            "request": request,
            "posts": posts,
            "followers_count": followers_count,
            "following_count": following_count
        })

    else:
        return HTMLResponse("<h3 style='color:white;'>Failed to fetch posts</h3>", status_code=500)

@app.get("/create_post", response_class=HTMLResponse)
async def get_create_post(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("create_post.html", {"request": request})

@app.post("/create_post", response_class=HTMLResponse)
async def create_post(request: Request, caption: str = Form(...), image: UploadFile = File(...)):
    try:
        token = request.cookies.get("token")
        if not token:
            return RedirectResponse("/login", status_code=302)

        user_info = requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
            json={"idToken": token}
        ).json()
        if "users" not in user_info:
            return RedirectResponse("/login", status_code=302)

        email = user_info["users"][0]["email"]
        file_data = await image.read()

        if len(file_data) > 2 * 1024 * 1024:
            return templates.TemplateResponse("create_post.html", {"request": request, "error": "Image too large!"})

        if not image.filename.lower().endswith(('.png', '.jpg')):
            return templates.TemplateResponse("create_post.html", {"request": request, "error": "Invalid file type!"})

        credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
        storage_client = storage.Client(credentials=credentials, project="creation-test-451610")
        bucket = storage_client.bucket("creation-test-451610.appspot.com")

        filename = f"{email}/{uuid.uuid4()}_{image.filename}"
        blob = bucket.blob(filename)
        blob.upload_from_string(file_data, content_type=image.content_type)

        image_url = f"https://storage.googleapis.com/creation-test-451610.appspot.com/{filename}"

        db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")
        post_data = {
            "Username": email,
            "Date": firestore.SERVER_TIMESTAMP,
            "Caption": caption,
            "ImageURL": image_url
        }
        post_ref = db.collection("Post").add(post_data)[1]  
        post_id = post_ref.id  

        return templates.TemplateResponse("create_post.html", {
            "request": request,
            "success": True,
            "image_url": image_url,
            "caption": caption
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("create_post.html", {"request": request, "error": "Unexpected error."})

@app.post("/toggle_follow", response_class=RedirectResponse)
async def toggle_follow(request: Request, target_email: str = Form(...)):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    user_info = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
        json={"idToken": token}
    ).json()

    if "users" not in user_info:
        return RedirectResponse("/login", status_code=302)

    current_email = user_info["users"][0]["email"]
    if current_email == target_email:
        return RedirectResponse("/", status_code=302)

    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    current_user_ref = db.collection("User").document(current_email)
    target_user_ref = db.collection("User").document(target_email)

    current_doc = current_user_ref.get()
    target_doc = target_user_ref.get()

    if not current_doc.exists or not target_doc.exists:
        return RedirectResponse("/", status_code=302)

    current_data = current_doc.to_dict()
    target_data = target_doc.to_dict()

    following_list = current_data.get("Following", [])
    followers_list = target_data.get("Followers", [])

    is_following = any(f.get("email") == target_email for f in following_list)

    if is_following:
        following_list = [f for f in following_list if f.get("email") != target_email]
        followers_list = [f for f in followers_list if f.get("email") != current_email]
    else:
        timestamp = datetime.utcnow().isoformat()
        following_list.append({"email": target_email, "timestamp": timestamp})
        followers_list.append({"email": current_email, "timestamp": timestamp})

    current_user_ref.update({"Following": following_list})
    target_user_ref.update({"Followers": followers_list})

    return RedirectResponse(url=f"/profile/{target_email}", status_code=303)

@app.get("/followers", response_class=HTMLResponse)
async def my_followers(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    user_info = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
        json={"idToken": token}
    ).json()

    if "users" not in user_info:
        return RedirectResponse("/login", status_code=302)

    current_email = user_info["users"][0]["email"]

    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    doc = db.collection("User").document(current_email).get()
    followers_raw = doc.to_dict().get("Followers", [])

    followers = []
    for entry in followers_raw:
        f_email = entry.get("email")
        timestamp = entry.get("timestamp", "")
        user_doc = db.collection("User").document(f_email).get()
        if user_doc.exists:
            name = user_doc.to_dict().get("ProfileName", f_email.split("@")[0])
            followers.append({"name": name, "timestamp": timestamp})

    sorted_followers = sorted(followers, key=lambda x: x["timestamp"], reverse=True)

    return templates.TemplateResponse("followers.html", {
        "request": request,
        "followers": sorted_followers
    })

@app.get("/following", response_class=HTMLResponse)
async def my_following(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    user_info = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
        json={"idToken": token}
    ).json()

    if "users" not in user_info:
        return RedirectResponse("/login", status_code=302)

    current_email = user_info["users"][0]["email"]

    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    doc = db.collection("User").document(current_email).get()
    following_raw = doc.to_dict().get("Following", [])

    following = []
    for entry in following_raw:
        f_email = entry.get("email")
        timestamp = entry.get("timestamp", "")
        user_doc = db.collection("User").document(f_email).get()
        if user_doc.exists:
            name = user_doc.to_dict().get("ProfileName", f_email.split("@")[0])
            following.append({"name": name, "timestamp": timestamp})

    sorted_following = sorted(following, key=lambda x: x["timestamp"], reverse=True)

    return templates.TemplateResponse("following.html", {
        "request": request,
        "following": sorted_following
    })

@app.get("/followers/{email}", response_class=HTMLResponse)
async def followers_of_user(request: Request, email: str):
    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    doc = db.collection("User").document(email).get()
    followers_raw = doc.to_dict().get("Followers", [])

    followers = []
    for entry in followers_raw:
        f_email = entry.get("email")
        timestamp = entry.get("timestamp", "")
        user_doc = db.collection("User").document(f_email).get()
        if user_doc.exists:
            name = user_doc.to_dict().get("ProfileName", f_email.split("@")[0])
            followers.append({"name": name, "timestamp": timestamp})

    sorted_followers = sorted(followers, key=lambda x: x["timestamp"], reverse=True)

    return templates.TemplateResponse("followers.html", {
        "request": request,
        "followers": sorted_followers
    })

@app.get("/following/{email}", response_class=HTMLResponse)
async def following_of_user(request: Request, email: str):
    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    doc = db.collection("User").document(email).get()
    following_raw = doc.to_dict().get("Following", [])

    following = []
    for entry in following_raw:
        f_email = entry.get("email")
        timestamp = entry.get("timestamp", "")
        user_doc = db.collection("User").document(f_email).get()
        if user_doc.exists:
            name = user_doc.to_dict().get("ProfileName", f_email.split("@")[0])
            following.append({"name": name, "timestamp": timestamp})

    sorted_following = sorted(following, key=lambda x: x["timestamp"], reverse=True)

    return templates.TemplateResponse("following.html", {
        "request": request,
        "following": sorted_following
    })

@app.get("/profile/{username}", response_class=HTMLResponse)
async def other_profile(username: str, request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    user_info = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
        json={"idToken": token}
    ).json()

    if "users" not in user_info:
        return RedirectResponse("/login", status_code=302)

    current_email = user_info["users"][0]["email"]

    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    target_user_doc = db.collection("User").document(username).get()

    followers_count = 0
    following_count = 0
    profile_name = username.split('@')[0] 

    if target_user_doc.exists:
        target_data = target_user_doc.to_dict()
        followers_count = len(target_data.get("Followers", []))
        following_count = len(target_data.get("Following", []))
        profile_name = target_data.get("ProfileName", profile_name)

    current_user_doc = db.collection("User").document(current_email).get()
    is_following = False
    if current_user_doc.exists:
        following_list = current_user_doc.to_dict().get("Following", [])
        is_following = any(f.get("email") == username for f in following_list)

    project_id = "assignment-3-d2d70"
    query_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents:runQuery"
    query_payload = {
        "structuredQuery": {
            "from": [{"collectionId": "Post"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "Username"},
                    "op": "EQUAL",
                    "value": {"stringValue": username}
                }
            },
            "orderBy": [{
                "field": {"fieldPath": "Date"},
                "direction": "DESCENDING"
            }]
        }
    }

    headers = {"Authorization": f"Bearer {get_service_token()}"}
    result = requests.post(query_url, json=query_payload, headers=headers)

    posts = []
    if result.status_code == 200:
        for doc in result.json():
            if "document" in doc:
                fields = doc["document"]["fields"]
                posts.append(fields)

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "posts": posts,
        "other_user": username,
        "is_following": is_following,
        "followers_count": followers_count,
        "following_count": following_count,
    })

@app.post("/add_comment")
async def add_comment(request: Request, post_id: str = Form(...), text: str = Form(...)):
    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    token = request.cookies.get("token")
    username = "Anonymous"
    if token:
        user_info = requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_WEB_API_KEY}",
            json={"idToken": token}
        ).json()
        if "users" in user_info:
            email = user_info["users"][0]["email"]
            username = email.split('@')[0]

    post_id_hash = hashlib.sha256(post_id.encode()).hexdigest()

    comments_ref = db.collection("Comments").document(post_id_hash).collection("PostComments")
    comments_ref.add({
        "Username": username,
        "Text": text,
        "Timestamp": firestore.SERVER_TIMESTAMP
    })

    return {"message": "Comment added successfully"}

@app.get("/get_comments")
async def get_comments(post_id: str):
    credentials = service_account.Credentials.from_service_account_file("firebase-credentials.json")
    db = firestore.Client(credentials=credentials, project="assignment-3-d2d70")

    post_id_hash = hashlib.sha256(post_id.encode()).hexdigest()

    comments_ref = db.collection("Comments").document(post_id_hash).collection("PostComments")
    comments = comments_ref.order_by("Timestamp", direction=firestore.Query.DESCENDING).stream()

    comment_list = []
    for comment in comments:
        data = comment.to_dict()
        comment_list.append({
            "username": data.get("Username", "Anonymous"),
            "text": data.get("Text", ""),
        })
    return comment_list

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
