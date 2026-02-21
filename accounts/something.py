import smtplib

server = smtplib.SMTP("smtp.zoho.com", 587)
server.starttls()
server.login("noreply@united-4-change.org", "S0iYCksfq6Cv")
print("Login successful")
server.quit()