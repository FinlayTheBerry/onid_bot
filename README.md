# WHAT IS ONIDbot?
🛡️ ONIDbot is a free and [open-source](https://github.com/FinlayTheBerry/ONIDbot) Discord bot that verifies your server's members using their [onid@oregonstate.edu](https://onid.oregonstate.edu) email addresses.  
👨‍💻 ONIDbot was developed by Finlay Christ, a cybersecurity major and president of the OSU Rock Climbing Club.  
🗓️ ONIDbot has been protecting clubs at Oregon State University since 9/26/2025.  
📈 ONIDbot has verified over 250 students and has blocked dozens of scammers and creeps.  
🫶 ONIDbot proudly protects the OSU Rock Climbing Club, OSU Hiking Club, OSU Conservation Club, and OSU App Development Club.  

# WHY USE ONIDbot?
Posting your club's Discord server invite to social media is a great way to grow your community, but as soon as that link becomes public, anyone can join. OSU clubs specifically have seen a massive increase in scammers and creeps. ONIDbot keeps your club members safe by restricting the access given to non-students.  

# HOW DO MEMBERS VERIFY?
Verifying with ONIDbot is easy. New members press the "Get Verified!" button, enter their onid@oregonstate.edu email address, receive a link in their inbox, and click that link. Once clicked, verification is complete and they get access to your server. For members who have already verified on a different server, pressing "Get Verified!" instantly grants access to your server-no email required.

# ONIDbot SETUP:

### 1️⃣ Adding The Bot/Permissions:
To add ONIDbot to your server, [click here](https://discord.com/oauth2/authorize?client_id=1487624623129497641) and follow Discord's instructions.  
ONIDbot asks for three permissions, each of which is essential for the bot to function correctly:  
- Manage Roles: Required to give members the "Verified" role after completing verification.  
- Send Messages: Required to post the "Get Verified!" button so members can click it.  

### 2️⃣ Roles Setup:
Next, you will need to create a role that is given to verified members.  
Go to Server Settings > Roles and press Create Role.  
Name the role exactly "Verified" and give that role the following permissions:  
View Channels, Send Messages and Create Posts, Read Message History, Connect, Speak, and Use Voice Activity.  
Then go to @everyone and press "Clear permissions" to remove all permissions.  
📝 NOTE: The ONIDbot role must be dragged above the Verified role for ONIDbot to function correctly.  

### 3️⃣ Get-Verified Channel Setup:
Next, create a new channel called get-verified.  
Go to Edit Channel > Permissions and set the following:  
- @everyone is granted View Channel and Read Message History.  
- @ONIDbot is granted Send Messages.  
- @Verified is denied Send Messages.  

Finally, type "/post_verification_button" in the get-verified channel to create the "Get Verified!" button.  
ONIDbot is now set up and verifying members!  
📝 NOTE: It is highly recommended to have a friend test out verification to ensure it is set up correctly.  

# FAQ
Q: Will existing members have to verify through ONIDbot?  
A: Nope! If you have already given the verified role to a member, ONIDbot won't take it away.  

Q: I like having some channels public. Will ONIDbot force everything to be private?  
A: Nope, you have total control over which channels and permissions require the verified role and which are given to everyone.  

Q: What should I do if I want to allow some non-students to join?  
A: Anyone with an active @oregonstate.edu email can verify through ONIDbot. Others can be given the verified role manually.  

Q: Who can verify with ONIDbot?  
A: ONIDbot can verify anyone with an @oregonstate.edu email address, so students, staff, faculty, and recently graduated alumni.  

Q: What should I do if I have another question that's not answered here?  
A: Send a Discord DM to @finlaytheberry or an email to [christj@oregonstate.edu](mailto:christj@oregonstate.edu).  

# 🔒 PRIVACY STATEMENT
ONIDbot stores the following information about you after verification: your ONID email address, your full name, and your Discord user ID.  
ONIDbot also collects logs which may include additional data relating to your interactions with the software.  
You can request the deletion of this data at any time by emailing [christj@oregonstate.edu](mailto:christj@oregonstate.edu).  
I respect your right to privacy. If you have additional questions or concerns, please reach out to [christj@oregonstate.edu](mailto:christj@oregonstate.edu).
