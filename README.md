Brightpearl
===========

Authentication
--------------
```python
>>> from brightpearl import API
>>> api = API('account_id')
>>> api.authenticate('user', 'passwd')
```
```python
>>> from brightpearl import API
>>> api = API('account_id', token='xxxxtoken')
```

Usage
-----
```python
>>> api.product.product.post(**data)
... [<brightpearl.Resource object at 0x1db1490>]
>>> product = api.product.product(1).get()[0]
>>> product.sku
... 'BOO34KALZ'
>>> search = api.product.product_search.get(SKU=product.sku)[0]
>>> search.results
... [['BOO34KALZ', 'T-Shirt Blue', ...]]
```
