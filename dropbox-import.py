import dropbox, os, sys
import datetime

class Commit(object):
    def __init__(self):
        self.last_mark = None
    
    def __lt__(self, other):
        return self.date < other.date
    
    def __str__(self):
        return """commit refs/heads/master
mark :{0.mark}
committer {0.committer} {1} {0.date:%z}
data {2}
{0.message}""".format(self, int(self.date.replace(tzinfo=datetime.timezone.utc).timestamp()), len(self.message))+("" if self.last_mark is None else "from : {0}".format(self.last_mark))

prefix = os.path.expanduser("~/.dropbox-git/")
if not os.path.isdir(prefix):
    os.mkdir(prefix)

app_key = open(prefix+"app-key").read().strip()
app_secret = open(prefix+"app-secret").read().strip()

if os.path.exists(prefix+"access-token"):
    access_token = open(prefix+"access-token").read().strip()
else:
    flow = dropbox.client.DropboxOAuth2FlowNoRedirect(app_key, app_secret)
    authorize_url = flow.start()
    print('1. Go to:', authorize_url, file=sys.stderr)
    try:
        import webbrowser
        webbrowser.open(authorize_url)
    except Exception:
        pass
    print('2. Click "Allow" (you might have to log in first)', file=sys.stderr)
    print('3. Copy the authorization code.', file=sys.stderr)
    print("Enter the authorization code here:", file=sys.stderr, end=' ')
    code = input().strip()
    # This will fail if the user enters an invalid authorization code
    access_token, user_id = flow.finish(code)
    open(prefix+"access-token", 'w').write(access_token)

client = dropbox.client.DropboxClient(access_token)

def explore_file(client, path, committer, commits):
    metadata = client.metadata(path, include_deleted=True)
    if metadata["is_dir"]:
        for subFile in metadata["contents"]:
            explore_file(client, subFile["path"], committer, commits)
    else:
        for revision in client.revisions(path):
            commit = Commit()
            commit.date = datetime.datetime.strptime(revision["modified"], "%a, %d %b %Y %H:%M:%S %z")
            commit.message = "Imported from Dropbox {0[path]} at {0[modified]}".format(revision)
            commit.committer = committer
            commit.mark = 0
            commit.path = revision["path"]
            commit.rev = revision["rev"]
            commit.deleted = "is_deleted" in revision and revision["is_deleted"]
            commits.append(commit)

commits = []
if len(sys.argv) == 2:
    root_path = sys.argv[1]
else:
    print("Enter a folder to explore:", file=sys.stderr, end=' ')
    root_path = input()
explore_file(client, root_path, "{0[display_name]} <{0[email]}>".format(client.account_info()), commits)
commits.sort()
for i, commit in enumerate(commits):
    commit.mark = i+1
    if i != 0:
        commit.last_mark = i

def casefold(s, target):
    result = list(s)
    for i in range(min(len(s), len(target))):
        if s[i].lower() == target[i] or s[i].upper() == target[i]:
            result[i] = target[i]
    return ''.join(result)

for commit in commits:
    print(commit)
    relpath = os.path.relpath(casefold(commit.path, root_path), root_path)
    if commit.deleted:
        print("D {0}".format(relpath))
    else:
        print("M 644 inline {0}".format(relpath))
        f = client.get_file(commit.path, rev=commit.rev)
        data = f.read()
        f.close()
        print("data {0}".format(len(data)))
        sys.stdout.flush()
        sys.stdout.buffer.flush()
        sys.stdout.buffer.write(data)
        print()

