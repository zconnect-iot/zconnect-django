import sys
from zconnect.pytesthook import get_test_settings

locals().update(get_test_settings())
SECRET_KEY = "abc123"

# project_dir = dirname(dirname(abspath(__file__)))
# sys.path.insert(0, project_dir)
# sys.path.insert(0, join(project_dir, 'tests'))
