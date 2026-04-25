import { useEffect, useState } from "react";
import { getProfile, updateProfile, changePassword } from "../utils/api";
import { Container, TextField, Button, Typography } from "@mui/material";

const Profile = () => {
  const [profile, setProfile] = useState({});
  const [passwords, setPasswords] = useState({});

  useEffect(() => {
    (async () => {
      const res = await getProfile();
      setProfile(res.data);
    })();
  }, []);

  const handleUpdate = async () => {
    await updateProfile(profile);
    alert("Profile Updated");
  };

  const handleChangePassword = async () => {
    await changePassword(passwords);
    alert("Password Changed");
  };

  return (
    <Container>
      <Typography variant="h5">Profile</Typography>
      <TextField label="First Name" value={profile.first_name} onChange={(e) => setProfile({ ...profile, first_name: e.target.value })} fullWidth />
      <Button onClick={handleUpdate} variant="contained">Update Profile</Button>
      
      <Typography variant="h6">Change Password</Typography>
      <TextField label="Old Password" type="password" fullWidth onChange={(e) => setPasswords({ ...passwords, old_password: e.target.value })} />
      <TextField label="New Password" type="password" fullWidth onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })} />
      <Button onClick={handleChangePassword} variant="contained">Change Password</Button>
    </Container>
  );
};

export default Profile;
