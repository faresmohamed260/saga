import {
    createUserWithEmailAndPassword,
    signInWithEmailAndPassword,
    signInWithPopup,
    GoogleAuthProvider,
    updateProfile,
    signOut
} from "firebase/auth";

import { auth } from "./firebase";

const provider = new GoogleAuthProvider();

export const signup = async (
    fullName,
    email,
    password
) => {
    const userCredential =
        await createUserWithEmailAndPassword(
            auth,
            email,
            password
        );

    await updateProfile(userCredential.user, {
        displayName: fullName,
    });

    return userCredential.user;
};

export const login = async (
    email,
    password
) => {
    const userCredential =
        await signInWithEmailAndPassword(
            auth,
            email,
            password
        );

    return userCredential.user;
};

export const googleLogin = async () => {
    const result = await signInWithPopup(
        auth,
        provider
    );

    return result.user;
};

export const logout = async () => {
    await signOut(auth);
};