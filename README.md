## OrviboS20AlexaSkill

VERSION v1.0 19/12/2017

***********************************

This is the code for an Alexa skill that allows you to turn on/off an Orvibo S20 wireless socket using voice commands on Alexa.
This skill requires no third party devices to run a server. everything runs on AWS using lambda, and it also allows for winding a timer to shut down the S20.
NOTICE: everything, including the shut down timer requires an internet connection, since this skill doesn't use the S20's internal timer, but one from AWS.

## Getting Started with OrviboS20AlexaSkill

The guide below was mostly copied from this link https://developer.amazon.com/alexa-skills-kit/alexa-skill-quick-start-tutorial. I recommend using both, Amazon's has screen shots.

## Step 1 (Create the IAM policy and role for the timer feature access permissions)

#### Creating the IAM policies for the Lambda function:

1. Navigate to IAM in your management console: https://console.aws.amazon.com/iam/home#/roles
2. Select "Policies" in the sidebar.
3. Click "Create Policy".
4. Select "Create Your Own Policy".
5. Enter an appropriate policy name and description like "wiwo_timer".
6. Paste the contents of [\AlexaSkillKit_Code\policy.txt](https://github.com/itaybia/OrviboS20AlexaSkill/blob/master/AlexaSkillKit_Code/policy.txt)
    * Notice that you need to edit the "Resource" item after you create the lambda function below with the TIMER_ARN.
7. Click "Create Policy".
8. Select "Create Your Own Policy".
9. Enter policy name "lambda_logging"
10. Paste the contents of [\AlexaSkillKit_Code\logs_policy.txt](https://github.com/itaybia/OrviboS20AlexaSkill/blob/master/AlexaSkillKit_Code/logs_policy.txt)

#### Creating the IAM role for the Lambda function:
1. Select "Role" in the sidebar.
2. Click "Create New Role".
3. Enter an appropriate role name ("wiwo_timer") and click "Next Step".
4. Select "AWS Lambda" within the AWS Service Roles.
5. Change the filter to "Customer Managed", check the box of the 2 policies you created above, and click "Next Step".
6. Click "Create Role".


## Step 2 (Create your AWS Lambda function that your skill will use)

1. Download or clone my OrviboS20AlexaSkill github project https://github.com/itaybia/OrviboS20AlexaSkill
2. Gather the information about your Orvibo S20 socket.
    * Connect the S20 to the power
    * Find the S20's MAC address and IP:
        * In your router, you can probably find the devices connected to it. The S20 is probably going to be written as: HF-LPB100.
        * On a computer in the same network, you can run: "ping HF-LPB100", and see the IP that was resolved. Then run "arp -a", and find the MAC address corresponding to the IP.
    * Setup port forwarding on your router to reach the S20's IP from above, and UDP port 10000. Remember which external port you configured. If you're already using the Wiwo app from the internet,
then you probably already have the external port configured to 10000. If you need help with configuring port forwarding, look here http://www.wikihow.com/Set-Up-Port-Forwarding-on-a-Router.
    * Get Your External IP, https://whatismyipaddress.com/ or a hostname that you have for your External IP (through noip, dyndns, etc.).
3. If you do not already have an account on AWS, go to Amazon Web Services and create an account.
4. Log in to the AWS Management Console and navigate to AWS Lambda.
5. Click the region drop-down in the upper-right corner of the console and select either **US East (N. Virginia)** or **EU (Ireland)**.
Lambda functions for Alexa skills must be hosted in either the **US East (N. Virginia)** or **EU (Ireland)** region.
6. If you have no Lambda functions yet, click **Get Started Now**. Otherwise, click **Create a Lambda Function**.
7. Enter a name for the lambda function. "wiwo" for example.
8. Under Runtime, select **Python 2.7**.
9. Select "choose an existing role", and below that select the role you created in Step 1.
10. Add an "Alexa skills kit" trigger.
11. Add a "CloudWatch Events" trigger.
    1. Under **Rule name** give something like "wiwo_timer"
    2. **Rule type** should be "Schedule expression"
    3. Under **Schedule expression** write: **cron(50 22 28 12 ? 2000)**. Which is essentially a time in the past, just as a placeholder.
    4. Disable the trigger.
    5. Click **Add**.
    6. Remember the event's arn (let's call it **TIMER_ARN**).
        * Copy the TIMER_ARN into the resource field in the wiwo_timer policy created in step 1.6
10. Click the name of your lambda function (from step 2.7 above). Under the **Lambda function** code section (leave as **Edit code inline** and then copy in my code.
The code can be found under [\AlexaSkillKit_Code\lambda_function.py](https://github.com/itaybia/OrviboS20AlexaSkill/blob/master/AlexaSkillKit_Code/lambda_function.py)
You will need to edit some variables in the code.
    * **WIWO_mac**: Is the MAC address of your S20 as you found in step 2.
    * **WIWO_port**: Your External IP as found in step 2.
    * **WIWO_ip**: The external port which was configured in the router's port forwarding in step 2.
    * **DEFAULT_TIMEOUT**: if positive, then when turning the S20 on, it will automatically turn off after this many minutes.
    * **WIWO_CLOUDWATCH_TIMEOUT_EVENT_ARN**: the TIMER_ARN from step 2.11.6.
    * **CHECK_APP_ID**: true if you want to add security and allow the function to be used only from your alexa skill, according to the ALEXA_SKILL_APP_ID below.
    * **ALEXA_SKILL_APP_ID**: if CHECK_APP_ID is true, then this ID will be matched against intent for this lambda function. You will be able to fill it after we create the skill in step 3.
11. You can test your function by using the **Configure test event**. Change the name of **Hello World** as needed and pasted the contents of [\AlexaSkillKit_Code\OrviboS20Lambda_TurnOnWithTimeoutTestEvent.xml](https://github.com/itaybia/OrviboS20AlexaSkill/blob/master/AlexaSkillKit_Code/OrviboS20Lambda_TurnOnWithTimeoutTestEvent.xml) and then **Save** and **Test**.
    * If all works you should see the socket turn on, and then turn off after 15 minutes.
    * You should probably set **CHECK_APP_ID** in the lambda function to **False** to test this. At least until you create the Alexa skill and have the actual App ID.
12. Notice the ARN written on the top right of the page. We'll call it **LAMBDA_ARN**. It should be something like: arn:aws:lambda:<zone>-1:#:function:wiwo.


## Step 3 (Create your Alexa Skill and link your Lambda function)

1. Sign in to the **Amazon developer portal**. If you haven’t done so already, you’ll need to create a free account. https://developer.amazon.com/edw/home.html#/
2. From the top navigation bar, select **Alexa**.
3. Under **Alexa Skills Kit**, choose **Get Started >**.
4. Choose **Add a New Skill**.
5. Name your skill. This is the name displayed to users in the Alexa app. Wiwo, Kitchen socket, Orvibo S20 are all good choices.
6. Create an invocation name. This is the word or phrase that users will speak to activate the skill. Something like socket, Kitchen socket, Orvibo S20 and so on (wiwo did not work well for me, Alexa did not really understand it). Click **Save**.
7. Choose **Next** to continue to development of the new skill.
8. In the **Intent Schema** box, paste the JSON code from [\AlexaSkillKit_Code\IntentSchema.txt](https://github.com/itaybia/OrviboS20AlexaSkill/blob/master/AlexaSkillKit_Code/IntentSchema.txt)
9. Skip over the **Custom Slot Types** section.
10. Under **Sample Utterances** paste in contents of [\AlexaSkillKit_Code\Utterances.txt](https://github.com/itaybia/OrviboS20AlexaSkill/blob/master/AlexaSkillKit_Code/Utterances.txt)
11. Choose **Next** and wait until the interaction model finishes loading, in no more than a few seconds
12. Select the Endpoint AWS Lambda ARN then paste your LAMBDA_ARN code from step 2.12. Then choose Next.
13. Under **Service Simulator** you can test the skill.  Write what you would have said to alexa to operate the skill. Logs can be found here https://console.aws.amazon.com/cloudwatch
14. There is no need to Publish the skill.


************
#### Examples:

* "Alexa, Tell INVOCATION_NAME to turn on"
* "Alexa, Tell INVOCATION_NAME to turn on for 15 minutes"
* "Alexa, Tell INVOCATION_NAME to open"
* "Alexa, Tell INVOCATION_NAME to stop"
