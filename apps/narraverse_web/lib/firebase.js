import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
    apiKey: "AIzaSyBXBPhW89Vaoa9XcBB2Ih_QzzM7vjGCxEc",
    authDomain: "narraverse-e8fa7.firebaseapp.com",
    projectId: "narraverse-e8fa7",
    storageBucket: "narraverse-e8fa7.firebasestorage.app",
    messagingSenderId: "108333086854",
    appId: "1:108333086854:web:4756106c240c31275b3907"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);