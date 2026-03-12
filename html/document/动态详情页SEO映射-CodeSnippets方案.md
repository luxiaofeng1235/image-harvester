# 动态详情页 SEO 映射 Code Snippets 方案

## 适用场景

- 当前详情页是一个固定 `Page`
- 页面通过 `?article_id=1096` 或 `?article=1096` 动态读取文章内容
- 前端可以动态渲染标题和正文
- 但 WordPress / Yoast 默认输出的 SEO 仍然是固定页面的 SEO

这个方案的目标是：

- 保留当前固定详情页模板
- 在 WordPress 服务端根据 `article_id` 读取原文章
- 把原文章已有的 Yoast SEO 字段映射到当前固定页面

## 方案说明

这段代码用于覆盖当前固定页面的：

- 页面标题 `title`
- `meta description`
- `canonical`
- `og:title`
- `og:description`
- `og:url`
- `og:image`
- `twitter:title`
- `twitter:description`
- `twitter:image`

注意：

- 这是服务端 SEO 覆盖，不是前端 JS 改标签
- 适合放进 `Code Snippets`
- 粘贴时不要加 `<?php`

## 页面 ID

当前动态详情页后台编辑地址为：

```text
https://www.zgzonre.com/wp-admin/post.php?post=1131&action=edit
```

所以当前固定页面 ID 是：

```text
1131
```

## Code Snippets 代码

```php
/**
 * 动态产品页 SEO 映射
 * 固定 Page + ?article_id=1096 / ?article=1096
 * 从原文章读取 Yoast SEO，映射到当前固定页面
 */

function zr_dynamic_detail_seo_replace_vars( $value, $post ) {
    $value = trim( (string) $value );

    if ( '' === $value ) {
        return '';
    }

    $replacements = array(
        '%%title%%'    => get_the_title( $post ),
        '%%page%%'     => '',
        '%%sep%%'      => ' - ',
        '%%sitename%%' => get_bloginfo( 'name' ),
    );

    $value = strtr( $value, $replacements );
    $value = wp_strip_all_tags( $value );
    $value = preg_replace( '/\s+/u', ' ', $value );
    $value = preg_replace( '/(?:\s*-\s*)+$/u', '', $value );

    return trim( $value );
}

function zr_dynamic_detail_seo_context() {
    static $context = null;

    if ( null !== $context ) {
        return $context;
    }

    $context = array(
        'enabled'        => false,
        'title'          => '',
        'description'    => '',
        'canonical'      => '',
        'og_title'       => '',
        'og_description' => '',
        'og_url'         => '',
        'og_image'       => '',
    );

    if ( is_admin() ) {
        return $context;
    }

    $dynamic_page_id = 1131;

    if ( ! is_page( $dynamic_page_id ) ) {
        return $context;
    }

    $article_id = 0;

    if ( isset( $_GET['article_id'] ) ) {
        $article_id = absint( wp_unslash( $_GET['article_id'] ) );
    }

    if ( ! $article_id && isset( $_GET['article'] ) ) {
        $article_id = absint( wp_unslash( $_GET['article'] ) );
    }

    if ( ! $article_id ) {
        return $context;
    }

    $post = get_post( $article_id );

    if ( ! ( $post instanceof WP_Post ) || 'publish' !== $post->post_status ) {
        return $context;
    }

    $site_name = get_bloginfo( 'name' );

    $title = zr_dynamic_detail_seo_replace_vars(
        get_post_meta( $article_id, '_yoast_wpseo_title', true ),
        $post
    );

    if ( '' === $title ) {
        $title = get_the_title( $post );
        if ( $site_name ) {
            $title .= ' - ' . $site_name;
        }
    }

    $description = trim( (string) get_post_meta( $article_id, '_yoast_wpseo_metadesc', true ) );

    if ( '' === $description ) {
        $fallback_text = has_excerpt( $post ) ? $post->post_excerpt : $post->post_content;
        $fallback_text = wp_strip_all_tags( strip_shortcodes( $fallback_text ) );
        $fallback_text = preg_replace( '/\s+/u', ' ', $fallback_text );
        $description   = wp_trim_words( trim( $fallback_text ), 48, '' );
    }

    $canonical = add_query_arg(
        'article_id',
        $article_id,
        get_permalink( $dynamic_page_id )
    );

    $og_title = zr_dynamic_detail_seo_replace_vars(
        get_post_meta( $article_id, '_yoast_wpseo_opengraph-title', true ),
        $post
    );

    if ( '' === $og_title ) {
        $og_title = $title;
    }

    $og_description = trim( (string) get_post_meta( $article_id, '_yoast_wpseo_opengraph-description', true ) );

    if ( '' === $og_description ) {
        $og_description = $description;
    }

    $og_image = get_the_post_thumbnail_url( $post, 'full' );
    if ( ! $og_image ) {
        $og_image = '';
    }

    $context = array(
        'enabled'        => true,
        'title'          => $title,
        'description'    => $description,
        'canonical'      => $canonical,
        'og_title'       => $og_title,
        'og_description' => $og_description,
        'og_url'         => $canonical,
        'og_image'       => $og_image,
    );

    return $context;
}

function zr_dynamic_detail_seo_value( $key, $default = '' ) {
    $context = zr_dynamic_detail_seo_context();

    if ( empty( $context['enabled'] ) ) {
        return $default;
    }

    return ( isset( $context[ $key ] ) && '' !== $context[ $key ] ) ? $context[ $key ] : $default;
}

function zr_dynamic_detail_filter_document_title( $title ) {
    return zr_dynamic_detail_seo_value( 'title', $title );
}

function zr_dynamic_detail_filter_wpseo_title( $title ) {
    return zr_dynamic_detail_seo_value( 'title', $title );
}

function zr_dynamic_detail_filter_wpseo_metadesc( $desc ) {
    return zr_dynamic_detail_seo_value( 'description', $desc );
}

function zr_dynamic_detail_filter_wpseo_canonical( $canonical ) {
    return zr_dynamic_detail_seo_value( 'canonical', $canonical );
}

function zr_dynamic_detail_filter_wpseo_og_title( $title ) {
    return zr_dynamic_detail_seo_value( 'og_title', $title );
}

function zr_dynamic_detail_filter_wpseo_og_desc( $desc ) {
    return zr_dynamic_detail_seo_value( 'og_description', $desc );
}

function zr_dynamic_detail_filter_wpseo_og_url( $url ) {
    return zr_dynamic_detail_seo_value( 'og_url', $url );
}

function zr_dynamic_detail_filter_wpseo_og_image( $image ) {
    return zr_dynamic_detail_seo_value( 'og_image', $image );
}

function zr_dynamic_detail_filter_wpseo_twitter_title( $title ) {
    return zr_dynamic_detail_seo_value( 'og_title', $title );
}

function zr_dynamic_detail_filter_wpseo_twitter_description( $desc ) {
    return zr_dynamic_detail_seo_value( 'og_description', $desc );
}

function zr_dynamic_detail_filter_wpseo_twitter_image( $image ) {
    return zr_dynamic_detail_seo_value( 'og_image', $image );
}

add_filter( 'pre_get_document_title', 'zr_dynamic_detail_filter_document_title', 20 );
add_filter( 'wpseo_title', 'zr_dynamic_detail_filter_wpseo_title', 20 );
add_filter( 'wpseo_metadesc', 'zr_dynamic_detail_filter_wpseo_metadesc', 20 );
add_filter( 'wpseo_canonical', 'zr_dynamic_detail_filter_wpseo_canonical', 20 );
add_filter( 'wpseo_opengraph_title', 'zr_dynamic_detail_filter_wpseo_og_title', 20 );
add_filter( 'wpseo_opengraph_desc', 'zr_dynamic_detail_filter_wpseo_og_desc', 20 );
add_filter( 'wpseo_opengraph_url', 'zr_dynamic_detail_filter_wpseo_og_url', 20 );
add_filter( 'wpseo_opengraph_image', 'zr_dynamic_detail_filter_wpseo_og_image', 20 );
add_filter( 'wpseo_twitter_title', 'zr_dynamic_detail_filter_wpseo_twitter_title', 20 );
add_filter( 'wpseo_twitter_description', 'zr_dynamic_detail_filter_wpseo_twitter_description', 20 );
add_filter( 'wpseo_twitter_image', 'zr_dynamic_detail_filter_wpseo_twitter_image', 20 );
```

## 使用步骤

1. 安装并启用 `Code Snippets`
2. 新建一个 PHP snippet
3. 运行范围选择：`Run snippet everywhere`
4. 粘贴上面的代码
5. 保存并启用
6. 清理页面缓存、缓存插件、CDN 缓存
7. 打开以下地址测试：

```text
https://www.zgzonre.com/detail-new?article_id=1096
```

## 测试检查项

打开页面源码，确认以下内容是否已变成对应文章的内容：

- `<title>`
- `<meta name="description">`
- `<link rel="canonical">`
- `<meta property="og:title">`
- `<meta property="og:description">`
- `<meta property="og:url">`

## 注意事项

- 这段代码只会在固定页面 `1131` 上生效
- 如果 URL 没有 `article_id` / `article` 参数，则不会覆盖原页面 SEO
- 如果文章本身没有配置 Yoast 标题或描述，会自动退回到文章标题和摘要/正文截取
- 当前 `canonical` 使用的是：

```text
https://www.zgzonre.com/detail-new?article_id=1096
```

如果以后改成更规范的伪静态路由，需要再同步修改 `canonical` 生成规则

## 当前结论

- 前端已经能动态渲染详情页内容
- 当前问题主要在于 SEO 仍然是固定页面 SEO
- 这段 `Code Snippets` 的作用是把原文章 SEO 映射到固定动态详情页
- 它属于后端层修正，不替代前端逻辑
