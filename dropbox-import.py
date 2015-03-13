import dropbox, os, sys
import datetime
import posixpath # for Dropbox API

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

def casefold(s, target):
    result = list(s)
    for i in range(min(len(s), len(target))):
        if s[i].lower() == target[i] or s[i].upper() == target[i]:
            result[i] = target[i]
    return ''.join(result)

def explore_file(client, path, root_path, committer, commits):
    metadata = client.metadata(path, include_deleted=True)
    if metadata["is_dir"]:
        for subFile in metadata["contents"]:
            explore_file(client, subFile["path"], root_path, committer, commits)
    else:
        try:
            revisions = client.revisions(path)
        except dropbox.rest.ErrorResponse:
            revisions = [metadata]
        for revision in revisions:
            commit = Commit()
            commit.path = revision["path"]
            commit.relpath = posixpath.relpath(casefold(revision["path"], root_path), root_path)
            commit.date = datetime.datetime.strptime(revision["modified"], "%a, %d %b %Y %H:%M:%S %z")
            commit.message = "Imported from Dropbox {0.relpath} at {1[modified]}".format(commit, revision)
            commit.committer = committer
            commit.mark = 0
            commit.rev = revision["rev"]
            commit.deleted = "is_deleted" in revision and revision["is_deleted"]
            commits.append(commit)

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

commits = []
if len(sys.argv) == 2:
    root_path = sys.argv[1]
else:
    print("Enter a Dropbox-relative folder to explore:", file=sys.stderr, end=' ')
    root_path = input()

root_path = posixpath.normpath(posixpath.join('/', root_path))

explore_file(client, root_path, root_path, "{0[display_name]} <{0[email]}>".format(client.account_info()), commits)
commits.sort()
for i, commit in enumerate(commits):
    commit.mark = i+1
    if i != 0:
        commit.last_mark = i

for commit in commits:
    print(commit)
    if commit.deleted:
        print("D {0}".format(commit.relpath))
    else:
        print("M 644 inline {0}".format(commit.relpath))
        f = client.get_file(commit.path, rev=commit.rev)
        data = f.read()
        f.close()
        print("data {0}".format(len(data)))
        sys.stdout.flush()
        sys.stdout.buffer.flush()
        sys.stdout.buffer.write(data)
        print()

