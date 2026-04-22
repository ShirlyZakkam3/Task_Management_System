import { initializeApp } from "https://www.gstatic.com/firebasejs/11.6.0/firebase-app.js";
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut
} from "https://www.gstatic.com/firebasejs/11.6.0/firebase-auth.js";

// Import config from separate file
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

window.addEventListener("load", () => {
  const signupBtn = document.getElementById("signup-btn");
  const loginBtn = document.getElementById("login-btn");
  const logoutBtn = document.getElementById("signout-btn");

  if (signupBtn) {
    signupBtn.onclick = () => {
      const email = document.getElementById("email").value;
      const password = document.getElementById("password").value;
      const errorBox = document.getElementById("error-box");

      createUserWithEmailAndPassword(auth, email, password)
        .then(() => {
          window.location.href = "/login";
        })
        .catch(error => {
          errorBox.innerText = formatFirebaseError(error.code);
        });
    };
  }

  if (loginBtn) {
    loginBtn.onclick = async () => {
      const email = document.getElementById("email").value;
      const password = document.getElementById("password").value;
      const errorBox = document.getElementById("error-box");

      try {
        const userCredential = await signInWithEmailAndPassword(auth, email, password);
        const token = await userCredential.user.getIdToken();

        document.cookie = `token=${token}; path=/; SameSite=Strict`;

        await fetch("/init_user", { method: "POST" });

        window.location.href = "/";
      } catch (error) {
        errorBox.innerText = formatFirebaseError(error.code);
      }
    };
  }

  if (logoutBtn) {
    logoutBtn.onclick = () => {
      signOut(auth).then(() => {
        document.cookie = "token=; path=/; SameSite=Strict";
        window.location.href = "/login";
      });
    };
  }
});

function formatFirebaseError(code) {
  const messages = {
    "auth/email-already-in-use": "This email is already registered.",
    "auth/invalid-email": "Invalid email format.",
    "auth/operation-not-allowed": "Account creation is disabled.",
    "auth/weak-password": "Password should be at least 6 characters.",
    "auth/user-not-found": "No user found with this email.",
    "auth/wrong-password": "Incorrect password.",
    default: "Something went wrong. Please try again."
  };
  return messages[code] || messages.default;
}