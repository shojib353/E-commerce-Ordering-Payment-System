import json
from django.core.cache import cache
from apps.catalog.models import Category

CACHE_KEY_CATEGORY_TREE = 'category_tree'
CACHE_TIMEOUT = 3600

def build_category_tree() -> dict:
    """
    Build category tree hierarchy as an adjacency list.
    Returns:
        dict: { "null": [root_ids], "parent_id": [child_ids] }
    """
    categories = Category.objects.all().values('id', 'parent_id')
    tree = {"null": []}
    
    for cat in categories:
        cat_id = cat['id']
        parent_id = cat['parent_id']
        
        if str(cat_id) not in tree:
            tree[str(cat_id)] = []
            
        if parent_id is None:
            tree["null"].append(cat_id)
        else:
            parent_str = str(parent_id)
            if parent_str not in tree:
                tree[parent_str] = []
            tree[parent_str].append(cat_id)
            
    return tree

def get_cached_category_tree() -> dict:
    """
    Fetch the category tree from cache or database.
    """
    cached_tree = cache.get(CACHE_KEY_CATEGORY_TREE)
    if cached_tree is not None:
        try:
            return json.loads(cached_tree)
        except (TypeError, json.JSONDecodeError):
            pass
            
    tree = build_category_tree()
    cache.set(CACHE_KEY_CATEGORY_TREE, json.dumps(tree), timeout=CACHE_TIMEOUT)
    return tree

def invalidate_category_tree_cache():
    """
    Invalidate category tree cache from Redis.
    """
    cache.delete(CACHE_KEY_CATEGORY_TREE)

def get_category_descendants_dfs(category_id: int) -> list[int]:
    """
    Use Depth First Search (DFS) to traverse the cached category tree and
    retrieve the IDs of all descendant categories (inclusive of the starting category).
    """
    tree = get_cached_category_tree()
    
    # Check if category_id exists in our tree or DB
    category_id_str = str(category_id)
    if category_id_str not in tree and not Category.objects.filter(id=category_id).exists():
        return []
        
    descendants = []
    stack = [category_id]
    
    while stack:
        curr = stack.pop()
        descendants.append(curr)
        
        curr_str = str(curr)
        # Add all children to the stack
        children = tree.get(curr_str, [])
        for child in children:
            stack.append(child)
            
    return descendants
