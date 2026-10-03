# Auth Testing Playbook

App supports BOTH JWT email/password and Emergent Google auth. Users share `users` collection keyed by `user_id`.

## JWT
curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@example.com","password":"admin123"}'
curl -b cookies.txt $API/api/auth/me

## Google (Emergent) - create test session
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({user_id: userId, email: 'test.user.' + Date.now() + '@example.com', name: 'Test User', auth_provider: 'google', created_at: new Date()});
db.user_sessions.insertOne({user_id: userId, session_token: sessionToken, expires_at: new Date(Date.now()+7*24*60*60*1000), created_at: new Date()});
print(sessionToken);
"
curl $API/api/auth/me -H "Authorization: Bearer <sessionToken>"
Browser: add cookie session_token (httpOnly, secure, sameSite None, path /).
